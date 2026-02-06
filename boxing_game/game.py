from __future__ import annotations

import random
from pathlib import Path

from boxing_game.models import CareerState
from boxing_game.modules.amateur_circuit import (
    apply_fight_result,
    current_tier,
    generate_opponent,
    pro_readiness_status,
)
from boxing_game.modules.experience_engine import boxer_experience_profile, total_career_fights
from boxing_game.modules.career_clock import advance_month
from boxing_game.modules.fight_sim_engine import simulate_amateur_fight, simulate_pro_fight
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import (
    apply_pro_fight_result,
    available_division_moves,
    change_division,
    current_division_lineal_champion,
    ensure_rankings,
    format_purse_breakdown,
    generate_pro_opponent,
    offer_purse,
    player_lineal_division,
    player_pound_for_pound_position,
    pro_tier,
    turn_pro,
)
from boxing_game.modules.pro_spending import (
    apply_rest_month,
    apply_standard_training,
    list_staff_upgrade_options,
    medical_recovery,
    purchase_staff_upgrade,
    special_training_camp,
    staff_summary_lines,
)
from boxing_game.modules.retirement_engine import evaluate_retirement
from boxing_game.modules.rating_engine import boxer_overall_rating
from boxing_game.modules.savegame import (
    SavegameError,
    delete_state,
    list_saves,
    load_state,
    save_state,
)
from boxing_game.modules.world_sim import simulate_world_month
from boxing_game.rules_registry import load_rule_set


def _prompt_non_empty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Input cannot be empty.")


def _prompt_int(prompt: str, minimum: int, maximum: int) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue

        if minimum <= value <= maximum:
            return value
        print(f"Value must be between {minimum} and {maximum}.")


def _advance_month(
    state: CareerState,
    months: int = 1,
    *,
    rng: random.Random | None = None,
) -> bool:
    randomizer = rng or random.Random()
    for _ in range(months):
        events = advance_month(state, months=1)
        for event in events:
            print(event)
        for world_event in simulate_world_month(state, rng=randomizer):
            print(f"World: {world_event}")
        retirement = evaluate_retirement(state, rng=randomizer)
        if retirement.newly_retired:
            print(f"Retirement: {retirement.reason}")
            return True
    return False


def _render_stats(state: CareerState) -> None:
    boxer = state.boxer
    stage = "pro" if state.pro_career.is_active else "amateur"
    overall_rating = boxer_overall_rating(
        boxer,
        stage=stage,
        pro_record=state.pro_career.record,
    )
    experience = boxer_experience_profile(boxer, pro_record=state.pro_career.record)
    fights_total = total_career_fights(boxer, pro_record=state.pro_career.record)
    print("\n== Boxer Profile ==")
    print(f"Name: {boxer.profile.name} ({boxer.profile.stance})")
    print(f"Age: {boxer.profile.age}")
    print(
        f"Height/Weight: {boxer.profile.height_ft}'{boxer.profile.height_in}\" / {boxer.profile.weight_lbs} lbs"
    )
    print(f"Division: {boxer.division}")
    print(
        (
            "Aging Profile: "
            f"Peak ~{boxer.aging_profile.peak_age}, "
            f"Decline Onset ~{boxer.aging_profile.decline_onset_age}, "
            f"Decline Severity x{boxer.aging_profile.decline_severity:.2f}, "
            f"IQ Growth x{boxer.aging_profile.iq_growth_factor:.2f}"
        )
    )
    print(f"Overall Rating: {overall_rating}")
    print(
        (
            f"Experience: {experience.points} XP | "
            f"Level {experience.level} ({experience.title}) | "
            f"Fight Bonus +{experience.fight_bonus:.2f}"
        )
    )
    if experience.next_level_points is None:
        print("Experience Progress: max level reached.")
    else:
        print(
            f"Experience Progress: {experience.points}/{experience.next_level_points} to next level"
        )
    print(f"Career Fights: {fights_total}")

    if state.pro_career.is_active:
        pro_record = state.pro_career.record
        print(
            f"Pro Record: {pro_record.wins}-{pro_record.losses}-{pro_record.draws} (KO {pro_record.kos})"
        )
        print(
            "Amateur Record: "
            f"{boxer.record.wins}-{boxer.record.losses}-{boxer.record.draws} (KO {boxer.record.kos})"
        )
        print(
            f"Promoter: {state.pro_career.promoter} | Focus Org: {state.pro_career.organization_focus}"
        )
        print(
            f"Balance: ${state.pro_career.purse_balance:,.2f} | "
            f"Total Earnings: ${state.pro_career.total_earnings:,.2f}"
        )
        print(f"Injury Risk: {boxer.injury_risk}/100")
        print("Staff:")
        for line in staff_summary_lines(state):
            print(f"  - {line}")
        print("Rankings:")
        for org_name, rank in state.pro_career.rankings.items():
            label = f"#{rank}" if rank is not None else "Unranked"
            print(f"  - {org_name}: {label}")
        print("Organization Champions (current division):")
        for org_name in ["WBC", "WBA", "IBF", "WBO"]:
            champion = state.pro_career.organization_champions.get(org_name, {}).get(
                state.boxer.division
            )
            defenses = state.pro_career.organization_defenses.get(org_name, {}).get(
                state.boxer.division,
                0,
            )
            champion_label = champion or "Vacant"
            print(f"  - {org_name}: {champion_label} (D{defenses})")
        p4p_rank, p4p_score = player_pound_for_pound_position(state)
        p4p_label = f"#{p4p_rank}" if p4p_rank is not None else "Outside Top 120"
        lineal_holder = current_division_lineal_champion(state) or "Vacant"
        player_lineal = player_lineal_division(state)
        if player_lineal is not None:
            defenses = state.pro_career.lineal_defenses.get(player_lineal, 0)
            print(f"Lineal: Champion at {player_lineal} ({defenses} defenses)")
        else:
            print("Lineal: Not champion")
        print(f"Current Division Lineal Champion: {lineal_holder}")
        print(f"P4P: {p4p_label} ({p4p_score:.2f})")
        if state.pro_career.last_world_news:
            print("World News:")
            for item in state.pro_career.last_world_news[-6:]:
                print(f"  - {item}")
        if state.is_retired:
            print(f"Status: RETIRED at age {state.retirement_age}")
            if state.retirement_reason:
                print(f"Retirement Reason: {state.retirement_reason}")
    else:
        print(
            f"Amateur Record: {boxer.record.wins}-{boxer.record.losses}-{boxer.record.draws} (KO {boxer.record.kos})"
        )
        print(f"Amateur Points: {boxer.amateur_points}")
        print(f"Injury Risk: {boxer.injury_risk}/100")
        if state.is_retired:
            print(f"Status: RETIRED at age {state.retirement_age}")
            if state.retirement_reason:
                print(f"Retirement Reason: {state.retirement_reason}")

    print(f"Popularity: {boxer.popularity} | Fatigue: {boxer.fatigue}")
    print("Stats:")
    for key, value in boxer.stats.to_dict().items():
        print(f"  - {key}: {value}")


def _new_career() -> CareerState:
    print("\nCreate Your Boxer")
    name = _prompt_non_empty("Name: ")

    while True:
        stance = input("Stance (orthodox/southpaw): ").strip().lower()
        if stance in {"orthodox", "southpaw"}:
            break
        print("Stance must be orthodox or southpaw.")

    height_ft = _prompt_int("Height feet (ft): ", 4, 7)
    height_in = _prompt_int("Height inches (in): ", 0, 11)
    weight_lbs = _prompt_int("Weight (lbs): ", 90, 300)

    boxer = create_boxer(
        name=name,
        stance=stance,
        height_ft=height_ft,
        height_in=height_in,
        weight_lbs=weight_lbs,
    )

    state = CareerState(boxer=boxer)
    state.amateur_progress.tier = "novice"

    print("\nBoxer created.")
    _render_stats(state)
    return state


def _load_career() -> CareerState | None:
    while True:
        slots = list_saves()
        if not slots:
            print("No saves found.")
            return None

        print("\nAvailable saves:")
        for idx, slot in enumerate(slots, start=1):
            print(f"{idx}. {slot}")

        choice = _prompt_int("Choose save number: ", 1, len(slots))
        selected = slots[choice - 1]

        print(f"\nSelected: {selected}")
        print("1. Load save")
        print("2. Delete save")
        print("3. Back")
        action = _prompt_int("Choose action: ", 1, 3)

        if action == 1:
            try:
                state = load_state(selected)
            except SavegameError as exc:
                print(f"Failed to load: {exc}")
                return None

            if state.pro_career.is_active:
                ensure_rankings(state)

            print(f"Loaded save: {selected}")
            return state

        if action == 2:
            confirm = input(f"Delete '{selected}'? This cannot be undone. (y/n): ").strip().lower()
            if confirm not in {"y", "yes"}:
                print("Delete canceled.")
                continue
            try:
                delete_state(selected)
            except SavegameError as exc:
                print(f"Delete failed: {exc}")
                return None
            print(f"Deleted save: {selected}")
            continue

        return None


def _save_career(state: CareerState) -> None:
    default_slot = state.boxer.profile.name.lower().replace(" ", "_")
    slot = input(f"Save slot [{default_slot}]: ").strip() or default_slot

    try:
        path = save_state(state, slot)
    except SavegameError as exc:
        print(f"Save failed: {exc}")
        return

    resolved = Path(path).resolve()
    try:
        display_path = resolved.relative_to(Path.cwd())
    except ValueError:
        display_path = resolved
    print(f"Saved to {display_path}")


def _run_training(state: CareerState) -> None:
    if state.is_retired:
        print("Career is retired. Training is unavailable.")
        return
    rules = load_rule_set("attribute_model")
    focuses = rules["training_focuses"]

    print("\nTraining focuses:")
    for idx, focus in enumerate(focuses, start=1):
        print(f"{idx}. {focus}")

    choice = _prompt_int("Pick training focus: ", 1, len(focuses))
    focus = focuses[choice - 1]

    details = apply_standard_training(state, focus)
    _advance_month(state)

    print(
        f"Training complete. Focus improved: {focus} | "
        f"Coach Bonus +{details['coach_bonus']} | "
        f"Fatigue +{details['fatigue_gain']} | Injury Risk +{details['injury_risk_gain']}"
    )


def _run_special_camp(state: CareerState) -> None:
    if state.is_retired:
        print("Career is retired. Training camp is unavailable.")
        return
    if not state.pro_career.is_active:
        print("Special camp is available only in pro career.")
        return

    rules = load_rule_set("attribute_model")
    focuses = rules["training_focuses"]
    print("\nSpecial Camp focuses:")
    for idx, focus in enumerate(focuses, start=1):
        print(f"{idx}. {focus}")

    choice = _prompt_int("Pick special camp focus: ", 1, len(focuses))
    focus = focuses[choice - 1]

    try:
        details = special_training_camp(state, focus)
    except ValueError as exc:
        print(exc)
        return

    _advance_month(state, months=int(details["months"]))
    print(
        (
            f"Special camp complete ({focus}). Cost ${details['cost']:,.2f} | "
            f"Coach Bonus +{details['coach_bonus']} | "
            f"Fatigue +{details['fatigue_gain']} | Injury Risk +{details['injury_risk_gain']} | "
            f"Balance ${state.pro_career.purse_balance:,.2f}"
        )
    )


def _run_medical_recovery(state: CareerState) -> None:
    if state.is_retired:
        print("Career is retired. Medical recovery is unavailable.")
        return
    if not state.pro_career.is_active:
        print("Medical recovery is available only in pro career.")
        return
    try:
        details = medical_recovery(state)
    except ValueError as exc:
        print(exc)
        return

    _advance_month(state, months=int(details["months"]))
    print(
        (
            f"Medical recovery complete. Cost ${details['cost']:,.2f} | "
            f"Fatigue -{details['fatigue_reduced']} | "
            f"Injury Risk -{details['injury_risk_reduced']} | "
            f"Balance ${state.pro_career.purse_balance:,.2f}"
        )
    )


def _run_staff_upgrade(state: CareerState) -> None:
    if state.is_retired:
        print("Career is retired. Staff upgrades are unavailable.")
        return
    if not state.pro_career.is_active:
        print("Staff upgrades are available only in pro career.")
        return

    options = list_staff_upgrade_options(state)
    actionable = [item for item in options if item.next_cost is not None]
    if not actionable:
        print("All staff upgrades are already at max level.")
        return

    print("\nStaff upgrades:")
    for idx, option in enumerate(actionable, start=1):
        print(
            f"{idx}. {option.label} L{option.level}/{option.max_level} "
            f"-> L{option.level + 1} (${option.next_cost:,.2f})"
        )

    choice = _prompt_int("Pick staff upgrade: ", 1, len(actionable))
    selected = actionable[choice - 1]
    try:
        result = purchase_staff_upgrade(state, selected.key)
    except ValueError as exc:
        print(exc)
        return

    print(
        (
            f"Upgraded {result['label']} to L{result['new_level']}/{result['max_level']} "
            f"for ${result['cost']:,.2f}. "
            f"Balance ${state.pro_career.purse_balance:,.2f}"
        )
    )


def _run_amateur_fight(state: CareerState, rng: random.Random) -> None:
    if state.is_retired:
        print("Career is retired. Fights are unavailable.")
        return
    tier = current_tier(state)
    opponent = generate_opponent(state, rng=rng)

    print("\n== Opponent ==")
    print(f"Name: {opponent.name}")
    print(f"Tier: {tier['name']} | Rating: {opponent.rating}")
    print(
        f"Record: {opponent.record.wins}-{opponent.record.losses}-{opponent.record.draws} (KO {opponent.record.kos})"
    )
    print(
        f"Height/Weight: {opponent.height_ft}'{opponent.height_in}\" / {opponent.weight_lbs} lbs | {opponent.stance}"
    )

    confirm = input("Accept fight? (y/n): ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("Fight declined.")
        return

    result = simulate_amateur_fight(
        state.boxer,
        opponent,
        rounds=int(tier["rounds"]),
        rng=rng,
    )

    xp_before = state.boxer.experience_points
    apply_fight_result(state, opponent, result)
    xp_gain = state.boxer.experience_points - xp_before
    experience = boxer_experience_profile(state.boxer, pro_record=state.pro_career.record)
    _advance_month(state, rng=rng)

    print("\n== Fight Result ==")
    print(f"Winner: {result.winner}")
    print(f"Method: {result.method}")
    print(f"Rounds Completed: {result.rounds_completed}")
    print(f"Experience gained: +{xp_gain} XP ({experience.title})")

    if result.scorecards:
        for idx, score in enumerate(result.scorecards, start=1):
            print(f"Judge {idx}: {score}")

    print("Round log:")
    for line in result.round_log:
        print(f"  - {line}")


def _run_pro_fight(state: CareerState, rng: random.Random) -> None:
    if state.is_retired:
        print("Career is retired. Fights are unavailable.")
        return
    tier = pro_tier(state)
    opponent = generate_pro_opponent(state, rng=rng)
    purse = offer_purse(state, opponent, rng=rng)
    opponent_rank = (
        f"#{opponent.ranking_position}"
        if opponent.ranking_position is not None
        else "Unranked"
    )
    lineal_flag = "Yes" if opponent.is_lineal_champion else "No"
    org_rank_labels = []
    for org_name, rank in opponent.organization_ranks.items():
        if rank is None:
            continue
        org_rank_labels.append(f"{org_name} #{rank}")
    org_rank_text = ", ".join(org_rank_labels) if org_rank_labels else "No listed body ranks"
    sanctioned = purse.get("sanctioning_bodies", [])
    sanctioned_text = ", ".join(str(item) for item in sanctioned) if isinstance(sanctioned, list) else ""

    print("\n== Pro Opponent ==")
    print(f"Name: {opponent.name}")
    print(f"Tier: {tier['name']} | Rating: {opponent.rating}")
    print(f"Focus Org Rank: {opponent_rank} | Lineal Champion: {lineal_flag}")
    print(f"Body Ranks: {org_rank_text}")
    print(
        f"Record: {opponent.record.wins}-{opponent.record.losses}-{opponent.record.draws} (KO {opponent.record.kos})"
    )
    print(
        f"Height/Weight: {opponent.height_ft}'{opponent.height_in}\" / {opponent.weight_lbs} lbs | {opponent.stance}"
    )
    print(
        "Purse Offer: "
        f"{format_purse_breakdown(purse)} | "
        f"Total Expenses ${purse['total_expenses']:,.2f}"
    )
    if sanctioned_text:
        print(f"Sanctioned Bodies: {sanctioned_text}")

    confirm = input("Accept pro fight? (y/n): ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("Fight declined.")
        return

    result = simulate_pro_fight(
        state.boxer,
        opponent,
        rounds=int(tier["rounds"]),
        rng=rng,
    )

    xp_before = state.boxer.experience_points
    new_rank = apply_pro_fight_result(state, opponent, result, purse)
    xp_gain = state.boxer.experience_points - xp_before
    experience = boxer_experience_profile(state.boxer, pro_record=state.pro_career.record)
    _advance_month(state, rng=rng)

    print("\n== Pro Fight Result ==")
    print(f"Winner: {result.winner}")
    print(f"Method: {result.method}")
    print(f"Rounds Completed: {result.rounds_completed}")
    rank_label = f"#{new_rank}" if new_rank is not None else "Unranked"
    print(f"{state.pro_career.organization_focus} Rank: {rank_label}")
    if isinstance(sanctioned, list) and sanctioned:
        print(f"Sanctioned Bodies: {', '.join(str(item) for item in sanctioned)}")
    print(f"Balance: ${state.pro_career.purse_balance:,.2f}")
    print(f"Experience gained: +{xp_gain} XP ({experience.title})")
    if state.history and state.history[-1].notes:
        print(f"Lineal: {state.history[-1].notes}")


def _rest(state: CareerState) -> None:
    if state.is_retired:
        print("Career is retired. Rest action is unavailable.")
        return
    details = apply_rest_month(state)
    _advance_month(state)
    print(
        "Recovery month completed. "
        f"Fatigue -{details['fatigue_reduced']} | Injury Risk -{details['injury_risk_reduced']}"
    )


def _turn_pro(state: CareerState, rng: random.Random) -> None:
    if state.is_retired:
        print("Career is retired. Turning pro is unavailable.")
        return
    try:
        details = turn_pro(state, rng=rng)
    except ValueError as exc:
        print(exc)
        return

    print("\nTurned pro.")
    print(f"Promoter: {details['promoter']}")
    print(f"Organization focus: {details['organization_focus']}")
    print(f"Signing bonus: ${int(details['signing_bonus']):,}")


def _change_division(state: CareerState, rng: random.Random) -> None:
    if state.is_retired:
        print("Career is retired. Division changes are unavailable.")
        return
    options = available_division_moves(state)
    if not options:
        print("No adjacent divisions available from current class.")
        return

    print("\nAvailable division moves:")
    for idx, division in enumerate(options, start=1):
        print(f"{idx}. {division}")
    choice = _prompt_int("Pick target division: ", 1, len(options))
    target = options[choice - 1]

    try:
        result = change_division(state, target, rng=rng)
    except ValueError as exc:
        print(exc)
        return

    seed_rank = result["seed_rank"]
    seed_label = f"~#{seed_rank}" if seed_rank is not None else "Unranked"
    print(
        (
            f"Division changed: {result['from_division']} -> {result['to_division']} | "
            f"seed {seed_label} | fatigue +{result['fatigue_gain']} | "
            f"injury +{result['injury_risk_gain']} | cut {result['cut_lbs']} lbs"
        )
    )
    if int(result["vacated_lineal"]) == 1:
        print("Lineal title vacated immediately in previous division.")
    if int(result.get("vacated_org_titles", 0)) > 0:
        print(f"Vacated organization titles: {int(result['vacated_org_titles'])}.")


def _career_loop(state: CareerState) -> None:
    rng = random.Random()

    while True:
        if state.is_retired:
            print(
                f"\n=== Career Month {state.month}, Year {state.year} | "
                f"Age {state.boxer.profile.age} | RETIRED ==="
            )
            if state.retirement_reason:
                print(state.retirement_reason)

            print("1. View boxer")
            print("2. Save game")
            print("3. Back to main menu")
            choice = _prompt_int("Choose action: ", 1, 3)
            if choice == 1:
                _render_stats(state)
            elif choice == 2:
                _save_career(state)
            elif choice == 3:
                return
            continue

        if state.pro_career.is_active:
            tier = pro_tier(state)
            record = state.pro_career.record
            tier_label = f"pro-{tier['name']}"
            record_label = f"{record.wins}-{record.losses}-{record.draws}"
        else:
            tier = current_tier(state)
            record = state.boxer.record
            tier_label = tier["name"]
            record_label = f"{record.wins}-{record.losses}-{record.draws}"

        print(
            f"\n=== Career Month {state.month}, Year {state.year} | "
            f"Age {state.boxer.profile.age} | Tier: {tier_label} | Record: {record_label} ==="
        )

        if not state.pro_career.is_active:
            readiness = pro_readiness_status(state)
            if readiness.is_ready:
                print("Pro-ready milestone reached. You can turn pro now.")
            else:
                print(
                    "Pro progress: "
                    f"Age {readiness.current_age}/{readiness.min_age} | "
                    f"Fights {readiness.current_fights}/{readiness.min_fights} | "
                    f"Points {readiness.current_points}/{readiness.min_points}"
                )

        if state.pro_career.is_active:
            print("1. View boxer")
            print("2. Train")
            print("3. Take pro fight")
            print("4. Change division")
            print("5. Special training camp")
            print("6. Medical recovery")
            print("7. Hire/upgrade staff")
            print("8. Rest month")
            print("9. Save game")
            print("10. Back to main menu")

            choice = _prompt_int("Choose action: ", 1, 10)

            if choice == 1:
                _render_stats(state)
            elif choice == 2:
                _run_training(state)
            elif choice == 3:
                _run_pro_fight(state, rng)
            elif choice == 4:
                _change_division(state, rng)
            elif choice == 5:
                _run_special_camp(state)
            elif choice == 6:
                _run_medical_recovery(state)
            elif choice == 7:
                _run_staff_upgrade(state)
            elif choice == 8:
                _rest(state)
            elif choice == 9:
                _save_career(state)
            elif choice == 10:
                return
        else:
            print("1. View boxer")
            print("2. Train")
            print("3. Take amateur fight")
            print("4. Turn pro")
            print("5. Rest month")
            print("6. Save game")
            print("7. Back to main menu")

            choice = _prompt_int("Choose action: ", 1, 7)

            if choice == 1:
                _render_stats(state)
            elif choice == 2:
                _run_training(state)
            elif choice == 3:
                _run_amateur_fight(state, rng)
            elif choice == 4:
                _turn_pro(state, rng)
            elif choice == 5:
                _rest(state)
            elif choice == 6:
                _save_career(state)
            elif choice == 7:
                return


def run() -> None:
    while True:
        print("\n=== Text Boxing Career ===")
        print("1. New career")
        print("2. Load career")
        print("3. Quit")

        choice = _prompt_int("Choose option: ", 1, 3)

        if choice == 1:
            state = _new_career()
            _career_loop(state)
        elif choice == 2:
            state = _load_career()
            if state is not None:
                _career_loop(state)
        elif choice == 3:
            print("Goodbye.")
            return
