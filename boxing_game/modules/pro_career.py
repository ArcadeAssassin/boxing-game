from __future__ import annotations

import random
from dataclasses import dataclass

from boxing_game.models import (
    CareerRecord,
    CareerState,
    FightHistoryEntry,
    FightResult,
    Opponent,
    ProCareer,
    Stats,
)
from boxing_game.modules.amateur_circuit import FIRST_NAMES, LAST_NAMES, STANCE_CHOICES, pro_ready
from boxing_game.modules.attribute_engine import build_stats
from boxing_game.modules.rating_engine import boxer_overall_rating
from boxing_game.modules.weight_class_engine import classify_weight
from boxing_game.rules_registry import load_rule_set


@dataclass(frozen=True)
class RankingEntry:
    rank: int
    name: str
    rating: int
    wins: int
    losses: int
    draws: int
    is_player: bool = False


def _clamp_stat(value: int) -> int:
    return max(20, min(95, value))


def _mean_stat(stats: Stats) -> float:
    values = list(stats.to_dict().values())
    return sum(values) / len(values)


def _organization_names() -> list[str]:
    return [str(item["name"]) for item in load_rule_set("pro_career")["organizations"]]


def _organization_config(name: str) -> dict:
    for item in load_rule_set("pro_career")["organizations"]:
        if str(item["name"]) == name:
            return item
    raise ValueError(f"Unknown organization: {name}")


def _ranking_slots(name: str) -> int:
    config = _organization_config(name)
    return max(1, int(config.get("ranking_slots", 40)))


def _total_pro_fights(state: CareerState) -> int:
    record = state.pro_career.record
    return record.wins + record.losses + record.draws


def _tier_by_fights(fight_count: int) -> dict:
    rules = load_rule_set("pro_career")
    for tier in rules["tiers"]:
        if int(tier["min_fights"]) <= fight_count <= int(tier["max_fights"]):
            return tier
    return rules["tiers"][-1]


def pro_tier(state: CareerState) -> dict:
    return _tier_by_fights(_total_pro_fights(state))


def ensure_rankings(state: CareerState) -> None:
    canonical = _organization_names()
    if state.pro_career.organization_focus not in canonical:
        state.pro_career.organization_focus = canonical[0]

    if not state.pro_career.rankings:
        state.pro_career.rankings = {name: None for name in canonical}
        return

    for name in canonical:
        if name not in state.pro_career.rankings:
            state.pro_career.rankings[name] = None


def _unique_ranked_name(randomizer: random.Random, used_names: set[str]) -> str:
    for _ in range(32):
        candidate = f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate

    idx = len(used_names) + 1
    fallback = f"Contender {idx}"
    used_names.add(fallback)
    return fallback


def rankings_snapshot(
    state: CareerState,
    organization: str,
    *,
    top_n: int = 15,
) -> list[RankingEntry]:
    if not state.pro_career.is_active:
        raise ValueError("Rankings are available after turning pro.")
    if top_n < 1:
        raise ValueError("top_n must be >= 1.")

    ensure_rankings(state)
    organization_name = organization.strip().upper()
    if organization_name not in _organization_names():
        raise ValueError(f"Unknown organization: {organization_name}")

    ranking_slots = _ranking_slots(organization_name)
    visible_count = min(top_n, ranking_slots)
    player_rank = state.pro_career.rankings.get(organization_name)
    player_record = state.pro_career.record
    player_rating = boxer_overall_rating(state.boxer, stage="pro")

    seed = (
        f"{state.boxer.profile.name}:{organization_name}:{state.year}:"
        f"{state.month}:{_total_pro_fights(state)}"
    )
    randomizer = random.Random(seed)
    used_names = {state.boxer.profile.name}

    entries: list[RankingEntry] = []
    for rank in range(1, ranking_slots + 1):
        if player_rank is not None and rank == player_rank:
            entries.append(
                RankingEntry(
                    rank=rank,
                    name=state.boxer.profile.name,
                    rating=player_rating,
                    wins=player_record.wins,
                    losses=player_record.losses,
                    draws=player_record.draws,
                    is_player=True,
                )
            )
            continue

        name = _unique_ranked_name(randomizer, used_names)
        rating = max(55, min(98, int(round(96 - ((rank - 1) * 0.95) + randomizer.gauss(0, 1.2)))))
        wins = max(8, 30 - rank + randomizer.randint(0, 16))
        losses = max(0, (rank // 8) + randomizer.randint(0, 5))
        draws = randomizer.randint(0, 3)
        entries.append(
            RankingEntry(
                rank=rank,
                name=name,
                rating=rating,
                wins=wins,
                losses=losses,
                draws=draws,
                is_player=False,
            )
        )

    visible_entries = entries[:visible_count]
    if player_rank is not None and player_rank > visible_count:
        visible_entries.append(entries[player_rank - 1])
    elif player_rank is None:
        visible_entries.append(
            RankingEntry(
                rank=0,
                name=state.boxer.profile.name,
                rating=player_rating,
                wins=player_record.wins,
                losses=player_record.losses,
                draws=player_record.draws,
                is_player=True,
            )
        )
    return visible_entries


def turn_pro(state: CareerState, rng: random.Random | None = None) -> dict[str, str | int]:
    if state.pro_career.is_active:
        raise ValueError("Boxer is already pro.")
    if not pro_ready(state):
        raise ValueError("Pro readiness not reached yet.")

    randomizer = rng or random.Random()
    rules = load_rule_set("pro_career")

    promoter = randomizer.choice(list(rules["promoters"]))
    organization_focus = randomizer.choice(_organization_names())
    bonus_cfg = rules["turn_pro"]
    signing_bonus = randomizer.randint(
        int(bonus_cfg["signing_bonus_min"]),
        int(bonus_cfg["signing_bonus_max"]),
    )

    state.pro_career = ProCareer(
        is_active=True,
        promoter=promoter,
        organization_focus=organization_focus,
        rankings={name: None for name in _organization_names()},
        record=CareerRecord(),
        purse_balance=float(signing_bonus),
        total_earnings=float(signing_bonus),
    )
    state.boxer.popularity += 3
    return {
        "promoter": promoter,
        "organization_focus": organization_focus,
        "signing_bonus": signing_bonus,
    }


def generate_pro_opponent(state: CareerState, rng: random.Random | None = None) -> Opponent:
    if not state.pro_career.is_active:
        raise ValueError("Turn pro before scheduling pro fights.")
    ensure_rankings(state)

    randomizer = rng or random.Random()
    tier = pro_tier(state)
    boxer = state.boxer
    weight_class = classify_weight(boxer.profile.weight_lbs)

    rating = randomizer.randint(
        int(tier["opponent_rating_min"]),
        int(tier["opponent_rating_max"]),
    )
    name = f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}"

    height_inches = max(
        58,
        min(84, randomizer.randint(weight_class.avg_height_in - 4, weight_class.avg_height_in + 4)),
    )
    height_ft = height_inches // 12
    height_in = height_inches % 12

    min_weight = max(weight_class.min_lbs, boxer.profile.weight_lbs - 5)
    max_weight = min(weight_class.max_lbs, boxer.profile.weight_lbs + 5)
    if min_weight > max_weight:
        min_weight, max_weight = weight_class.min_lbs, weight_class.max_lbs

    weight_lbs = randomizer.randint(min_weight, max_weight)
    base_stats = build_stats(
        height_inches=height_inches,
        weight_lbs=weight_lbs,
        weight_class=weight_class,
    )
    shift = int(round((rating - _mean_stat(base_stats)) * 0.6))
    adjusted = {k: _clamp_stat(v + shift) for k, v in base_stats.to_dict().items()}

    wins = max(2, rating // 6 + randomizer.randint(0, 6))
    losses = max(0, wins // 4 + randomizer.randint(0, 4))

    return Opponent(
        name=name,
        age=randomizer.randint(20, 38),
        stance=randomizer.choice(STANCE_CHOICES),
        height_ft=height_ft,
        height_in=height_in,
        weight_lbs=weight_lbs,
        division=boxer.division,
        stats=Stats.from_dict(adjusted),
        rating=rating,
        record=CareerRecord(
            wins=wins,
            losses=losses,
            draws=randomizer.randint(0, 3),
            kos=max(1, wins // 2),
        ),
    )


def offer_purse(
    state: CareerState,
    opponent: Opponent,
    rng: random.Random | None = None,
) -> dict[str, float]:
    if not state.pro_career.is_active:
        raise ValueError("Turn pro before requesting a purse offer.")
    ensure_rankings(state)

    randomizer = rng or random.Random()
    rules = load_rule_set("pro_career")
    tier = pro_tier(state)
    economy = rules["economy"]
    purse_cfg = tier["purse"]

    base = randomizer.randint(int(purse_cfg["min"]), int(purse_cfg["max"]))
    popularity_bonus = state.boxer.popularity * float(economy["popularity_bonus_per_point"])
    rating_bonus = opponent.rating * float(economy["opponent_rating_bonus"])

    focus_org = state.pro_career.organization_focus
    current_rank = state.pro_career.rankings.get(focus_org)
    rank_bonus = 0.0
    if current_rank is not None:
        rank_bonus = max(0.0, (41 - current_rank) * float(economy["ranking_bonus_per_step"]))

    gross = float(base + popularity_bonus + rating_bonus + rank_bonus)

    manager_cut = gross * float(economy["manager_cut_pct"])
    trainer_cut = gross * float(economy["trainer_cut_pct"])
    camp_cost = gross * float(economy["camp_cost_pct"])
    commission_cut = gross * float(economy["commission_pct"])

    sanction_fee = 0.0
    org_cfg = _organization_config(focus_org)
    threshold = int(org_cfg["sanction_fee_rank_threshold"])
    if current_rank is not None and current_rank <= threshold:
        sanction_fee = gross * float(org_cfg["sanction_fee_pct"])

    net = gross - manager_cut - trainer_cut - camp_cost - commission_cut - sanction_fee
    total_expenses = manager_cut + trainer_cut + camp_cost + commission_cut + sanction_fee

    return {
        "gross": round(gross, 2),
        "manager_cut": round(manager_cut, 2),
        "trainer_cut": round(trainer_cut, 2),
        "camp_cost": round(camp_cost, 2),
        "commission_cut": round(commission_cut, 2),
        "sanction_fee": round(sanction_fee, 2),
        "total_expenses": round(total_expenses, 2),
        "net": round(max(0.0, net), 2),
    }


def format_purse_breakdown(purse_breakdown: dict[str, float]) -> str:
    return (
        f"Gross ${purse_breakdown['gross']:,.2f} | "
        f"Manager ${purse_breakdown['manager_cut']:,.2f} | "
        f"Trainer ${purse_breakdown['trainer_cut']:,.2f} | "
        f"Camp ${purse_breakdown['camp_cost']:,.2f} | "
        f"Commission ${purse_breakdown['commission_cut']:,.2f} | "
        f"Sanction ${purse_breakdown['sanction_fee']:,.2f} | "
        f"Net ${purse_breakdown['net']:,.2f}"
    )


def _update_focus_ranking(state: CareerState, result: FightResult) -> int | None:
    ensure_rankings(state)
    tier = pro_tier(state)
    ranking_cfg = tier["ranking"]
    boxer_name = state.boxer.profile.name
    focus_org = state.pro_career.organization_focus
    ranking_slots = _ranking_slots(focus_org)

    current_rank = state.pro_career.rankings.get(focus_org)
    new_rank = current_rank

    if result.winner == boxer_name:
        if current_rank is None:
            new_rank = int(ranking_cfg["entry_on_win"])
        else:
            new_rank = max(1, current_rank - int(ranking_cfg["win_step"]))
    elif result.winner == "Draw":
        if current_rank is not None:
            new_rank = min(ranking_slots, current_rank + int(ranking_cfg["draw_penalty"]))
    else:
        if current_rank is not None:
            new_rank = min(ranking_slots, current_rank + int(ranking_cfg["loss_penalty"]))

    if new_rank is not None:
        new_rank = max(1, min(ranking_slots, int(new_rank)))

    state.pro_career.rankings[focus_org] = new_rank
    return new_rank


def apply_pro_fight_result(
    state: CareerState,
    opponent: Opponent,
    result: FightResult,
    purse_breakdown: dict[str, float],
) -> int | None:
    if not state.pro_career.is_active:
        raise ValueError("Turn pro before applying pro results.")
    ensure_rankings(state)

    record = state.pro_career.record
    boxer_name = state.boxer.profile.name
    tier = pro_tier(state)
    popularity_cfg = tier["popularity"]

    if result.winner == boxer_name:
        record.wins += 1
        state.boxer.popularity += int(popularity_cfg["win"])
        if result.method in {"KO", "TKO"}:
            record.kos += 1
    elif result.winner == "Draw":
        record.draws += 1
        state.boxer.popularity += int(popularity_cfg["draw"])
    else:
        record.losses += 1
        state.boxer.popularity = max(1, state.boxer.popularity + int(popularity_cfg["loss"]))

    state.pro_career.purse_balance += float(purse_breakdown["net"])
    state.pro_career.total_earnings += float(purse_breakdown["gross"])
    state.boxer.fatigue = min(12, state.boxer.fatigue + 4)

    new_rank = _update_focus_ranking(state, result)

    state.history.append(
        FightHistoryEntry(
            opponent_name=opponent.name,
            opponent_rating=opponent.rating,
            result=result,
            stage="pro",
            purse=float(purse_breakdown["net"]),
        )
    )
    return new_rank
