from __future__ import annotations

import random
from dataclasses import dataclass

from boxing_game.constants import STARTING_AGE
from boxing_game.models import (
    CareerRecord,
    CareerState,
    FightHistoryEntry,
    FightResult,
    Opponent,
    Stats,
)
from boxing_game.modules.attribute_engine import build_stats
from boxing_game.modules.weight_class_engine import classify_weight
from boxing_game.rules_registry import load_rule_set

FIRST_NAMES = [
    "Alex",
    "Marcus",
    "Daniel",
    "Ramon",
    "Victor",
    "Tyrell",
    "Julian",
    "Andrei",
    "Caleb",
    "Javier",
    "Noah",
    "Darius",
    "Emilio",
    "Kendrick",
    "Owen",
]

LAST_NAMES = [
    "Cruz",
    "Foster",
    "Mendez",
    "Khan",
    "Diaz",
    "Porter",
    "Ward",
    "Ibarra",
    "Silva",
    "Bennett",
    "Choi",
    "Petrov",
    "Hughes",
    "Navarro",
    "Sims",
]

STANCE_CHOICES = ["orthodox", "southpaw"]


@dataclass(frozen=True)
class ProReadinessStatus:
    current_age: int
    current_fights: int
    current_points: int
    min_age: int
    min_fights: int
    min_points: int

    @property
    def is_ready(self) -> bool:
        return (
            self.current_age >= self.min_age
            and self.current_fights >= self.min_fights
            and self.current_points >= self.min_points
        )


def _clamp_stat(value: int) -> int:
    return max(20, min(95, value))


def _mean_stat(stats: Stats) -> float:
    values = list(stats.to_dict().values())
    return sum(values) / len(values)


def _current_tier_by_fights(fights_taken: int) -> dict:
    rules = load_rule_set("amateur_progression")
    for tier in rules["tiers"]:
        if int(tier["min_fights"]) <= fights_taken <= int(tier["max_fights"]):
            return tier
    return rules["tiers"][-1]


def current_tier(state: CareerState) -> dict:
    return _current_tier_by_fights(state.amateur_progress.fights_taken)


def generate_opponent(state: CareerState, rng: random.Random | None = None) -> Opponent:
    if state.pro_career.is_active:
        raise ValueError("Amateur opponents are unavailable after turning pro.")

    randomizer = rng or random.Random()
    tier = current_tier(state)

    boxer = state.boxer
    weight_class = classify_weight(boxer.profile.weight_lbs)

    rating = randomizer.randint(
        int(tier["opponent_rating_min"]),
        int(tier["opponent_rating_max"]),
    )

    name = f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}"
    height_inches = max(
        56,
        min(84, randomizer.randint(weight_class.avg_height_in - 3, weight_class.avg_height_in + 3)),
    )
    height_ft = height_inches // 12
    height_in = height_inches % 12

    min_weight = max(weight_class.min_lbs, boxer.profile.weight_lbs - 3)
    max_weight = min(weight_class.max_lbs, boxer.profile.weight_lbs + 3)
    if min_weight > max_weight:
        min_weight, max_weight = weight_class.min_lbs, weight_class.max_lbs

    weight_lbs = randomizer.randint(min_weight, max_weight)

    base_stats = build_stats(
        height_inches=height_inches,
        weight_lbs=weight_lbs,
        weight_class=weight_class,
    )

    current_mean = _mean_stat(base_stats)
    shift = int(round((rating - current_mean) * 0.45))

    adjusted = {k: _clamp_stat(v + shift) for k, v in base_stats.to_dict().items()}
    stats = Stats.from_dict(adjusted)

    wins = max(0, rating // 12 + randomizer.randint(-2, 4))
    losses = max(0, wins // 3 + randomizer.randint(0, 3))

    return Opponent(
        name=name,
        age=randomizer.randint(18, 29),
        stance=randomizer.choice(STANCE_CHOICES),
        height_ft=height_ft,
        height_in=height_in,
        weight_lbs=weight_lbs,
        division=boxer.division,
        stats=stats,
        rating=rating,
        record=CareerRecord(wins=wins, losses=losses, draws=randomizer.randint(0, 2), kos=max(0, wins // 2)),
    )


def apply_fight_result(
    state: CareerState,
    opponent: Opponent,
    result: FightResult,
) -> None:
    if state.pro_career.is_active:
        raise ValueError("Amateur fights are unavailable after turning pro.")

    tier = current_tier(state)
    points_cfg = tier["points"]
    boxer_name = state.boxer.profile.name

    if result.winner == boxer_name:
        state.boxer.record.wins += 1
        state.boxer.amateur_points += int(points_cfg["win"])
        if result.method in {"KO", "TKO"}:
            state.boxer.record.kos += 1
            state.boxer.amateur_points += int(points_cfg.get("ko_bonus", 0))
        state.boxer.popularity += 2
    elif result.winner == "Draw":
        state.boxer.record.draws += 1
        state.boxer.amateur_points += int(points_cfg["draw"])
        state.boxer.popularity += 1
    else:
        state.boxer.record.losses += 1
        state.boxer.amateur_points += int(points_cfg["loss"])
        state.boxer.popularity = max(1, state.boxer.popularity - 1)

    state.boxer.fatigue = min(12, state.boxer.fatigue + 3)

    state.history.append(
        FightHistoryEntry(
            opponent_name=opponent.name,
            opponent_rating=opponent.rating,
            result=result,
            stage="amateur",
            purse=0.0,
        )
    )

    state.amateur_progress.fights_taken += 1
    state.amateur_progress.tier = _current_tier_by_fights(
        state.amateur_progress.fights_taken
    )["name"]


def pro_readiness_status(state: CareerState) -> ProReadinessStatus:
    readiness = load_rule_set("amateur_progression")["pro_readiness"]
    min_age = int(readiness.get("min_age", STARTING_AGE))
    return ProReadinessStatus(
        current_age=state.boxer.profile.age,
        current_fights=state.amateur_progress.fights_taken,
        current_points=state.boxer.amateur_points,
        min_age=min_age,
        min_fights=int(readiness["min_fights"]),
        min_points=int(readiness["min_points"]),
    )


def pro_ready(state: CareerState) -> bool:
    return pro_readiness_status(state).is_ready
