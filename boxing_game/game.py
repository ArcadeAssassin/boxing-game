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
from boxing_game.modules.attribute_engine import training_gain
from boxing_game.modules.career_clock import advance_month
from boxing_game.modules.fight_sim_engine import simulate_amateur_fight, simulate_pro_fight
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import (
    apply_pro_fight_result,
    ensure_rankings,
    format_purse_breakdown,
    generate_pro_opponent,
    offer_purse,
    pro_tier,
    turn_pro,
)
from boxing_game.modules.rating_engine import boxer_overall_rating
from boxing_game.modules.savegame import SavegameError, list_saves, load_state, save_state
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


def _advance_month(state: CareerState, months: int = 1) -> None:
    events = advance_month(state, months=months)
    for event in events:
        print(event)


def _render_stats(state: CareerState) -> None:
    boxer = state.boxer
    stage = "pro" if state.pro_career.is_active else "amateur"
    overall_rating = boxer_overall_rating(boxer, stage=stage)
    print("\n== Boxer Profile ==")
    print(f"Name: {boxer.profile.name} ({boxer.profile.stance})")
    print(f"Age: {boxer.profile.age}")
    print(
        f"Height/Weight: {boxer.profile.height_ft}'{boxer.profile.height_in}\" / {boxer.profile.weight_lbs} lbs"
    )
    print(f"Division: {boxer.division}")
    print(f"Overall Rating: {overall_rating}")

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
        print("Rankings:")
        for org_name, rank in state.pro_career.rankings.items():
            label = f"#{rank}" if rank is not None else "Unranked"
            print(f"  - {org_name}: {label}")
    else:
        print(
            f"Amateur Record: {boxer.record.wins}-{boxer.record.losses}-{boxer.record.draws} (KO {boxer.record.kos})"
        )
        print(f"Amateur Points: {boxer.amateur_points}")

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
    slots = list_saves()
    if not slots:
        print("No saves found.")
        return None

    print("\nAvailable saves:")
    for idx, slot in enumerate(slots, start=1):
        print(f"{idx}. {slot}")

    choice = _prompt_int("Choose save number: ", 1, len(slots))
    selected = slots[choice - 1]

    try:
        state = load_state(selected)
    except SavegameError as exc:
        print(f"Failed to load: {exc}")
        return None

    if state.pro_career.is_active:
        ensure_rankings(state)

    print(f"Loaded save: {selected}")
    return state


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
    rules = load_rule_set("attribute_model")
    focuses = rules["training_focuses"]

    print("\nTraining focuses:")
    for idx, focus in enumerate(focuses, start=1):
        print(f"{idx}. {focus}")

    choice = _prompt_int("Pick training focus: ", 1, len(focuses))
    focus = focuses[choice - 1]

    state.boxer.stats = training_gain(state.boxer.stats, focus)
    state.boxer.fatigue = min(12, state.boxer.fatigue + 1)
    _advance_month(state)

    print(f"Training complete. Focus improved: {focus}")


def _run_amateur_fight(state: CareerState, rng: random.Random) -> None:
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

    apply_fight_result(state, opponent, result)
    _advance_month(state)

    print("\n== Fight Result ==")
    print(f"Winner: {result.winner}")
    print(f"Method: {result.method}")
    print(f"Rounds Completed: {result.rounds_completed}")

    if result.scorecards:
        for idx, score in enumerate(result.scorecards, start=1):
            print(f"Judge {idx}: {score}")

    print("Round log:")
    for line in result.round_log:
        print(f"  - {line}")


def _run_pro_fight(state: CareerState, rng: random.Random) -> None:
    tier = pro_tier(state)
    opponent = generate_pro_opponent(state, rng=rng)
    purse = offer_purse(state, opponent, rng=rng)

    print("\n== Pro Opponent ==")
    print(f"Name: {opponent.name}")
    print(f"Tier: {tier['name']} | Rating: {opponent.rating}")
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

    new_rank = apply_pro_fight_result(state, opponent, result, purse)
    _advance_month(state)

    print("\n== Pro Fight Result ==")
    print(f"Winner: {result.winner}")
    print(f"Method: {result.method}")
    print(f"Rounds Completed: {result.rounds_completed}")
    rank_label = f"#{new_rank}" if new_rank is not None else "Unranked"
    print(f"{state.pro_career.organization_focus} Rank: {rank_label}")
    print(f"Balance: ${state.pro_career.purse_balance:,.2f}")


def _rest(state: CareerState) -> None:
    state.boxer.fatigue = max(0, state.boxer.fatigue - 3)
    _advance_month(state)
    print("Recovery month completed.")


def _turn_pro(state: CareerState, rng: random.Random) -> None:
    try:
        details = turn_pro(state, rng=rng)
    except ValueError as exc:
        print(exc)
        return

    print("\nTurned pro.")
    print(f"Promoter: {details['promoter']}")
    print(f"Organization focus: {details['organization_focus']}")
    print(f"Signing bonus: ${int(details['signing_bonus']):,}")


def _career_loop(state: CareerState) -> None:
    rng = random.Random()

    while True:
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
            print("4. Rest month")
            print("5. Save game")
            print("6. Back to main menu")

            choice = _prompt_int("Choose action: ", 1, 6)

            if choice == 1:
                _render_stats(state)
            elif choice == 2:
                _run_training(state)
            elif choice == 3:
                _run_pro_fight(state, rng)
            elif choice == 4:
                _rest(state)
            elif choice == 5:
                _save_career(state)
            elif choice == 6:
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
