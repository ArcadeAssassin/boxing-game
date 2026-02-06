"""Amateur opponent generation, fight result application, and pro readiness.

Manages the amateur phase of a boxing career including tier progression,
opponent generation, point accumulation, and pro-readiness checks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from boxing_game.constants import MAX_FATIGUE, MAX_INJURY_RISK, STARTING_AGE
from boxing_game.models import (
    CareerRecord,
    CareerState,
    FightHistoryEntry,
    FightResult,
    Opponent,
    Stats,
)
from boxing_game.modules.attribute_engine import build_stats
from boxing_game.modules.experience_engine import add_experience_points, fight_experience_gain
from boxing_game.modules.fight_aftermath import calculate_post_fight_impact
from boxing_game.modules.pro_spending import adjusted_fatigue_gain, adjusted_injury_risk_gain
from boxing_game.modules.weight_class_engine import classify_weight
from boxing_game.rules_registry import load_rule_set
from boxing_game.utils import clamp_stat

# ---------------------------------------------------------------------------
# Name pools for opponent generation
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Alex", "Marcus", "Daniel", "Ramon", "Victor",
    "Tyrell", "Julian", "Andrei", "Caleb", "Javier",
    "Noah", "Darius", "Emilio", "Kendrick", "Owen",
]

LAST_NAMES = [
    "Cruz", "Foster", "Mendez", "Khan", "Diaz",
    "Porter", "Ward", "Ibarra", "Silva", "Bennett",
    "Choi", "Petrov", "Hughes", "Navarro", "Sims",
]

STANCE_CHOICES = ["orthodox", "southpaw"]


# ---------------------------------------------------------------------------
# Pro readiness
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProReadinessStatus:
    """Snapshot of the player's current vs. required pro-gate metrics."""

    current_age: int
    current_fights: int
    current_points: int
    min_age: int
    min_fights: int
    min_points: int

    @property
    def is_ready(self) -> bool:
        """``True`` when every gate requirement is satisfied."""
        return (
            self.current_age >= self.min_age
            and self.current_fights >= self.min_fights
            and self.current_points >= self.min_points
        )


# ---------------------------------------------------------------------------
# Stat helpers
# ---------------------------------------------------------------------------

def _mean_stat(stats: Stats) -> float:
    values = list(stats.to_dict().values())
    return sum(values) / len(values)


# ---------------------------------------------------------------------------
# Tier resolution
# ---------------------------------------------------------------------------

def _current_tier_by_fights(fights_taken: int) -> dict:
    rules = load_rule_set("amateur_progression")
    for tier in rules["tiers"]:
        if int(tier["min_fights"]) <= fights_taken <= int(tier["max_fights"]):
            return tier
    return rules["tiers"][-1]


def current_tier(state: CareerState) -> dict:
    """Return the amateur tier dict for the player's current fight count."""
    return _current_tier_by_fights(state.amateur_progress.fights_taken)


# ---------------------------------------------------------------------------
# Opponent generation
# ---------------------------------------------------------------------------

def generate_opponent(state: CareerState, rng: random.Random | None = None) -> Opponent:
    """Generate a randomised amateur opponent appropriate for the current tier.

    Raises ``ValueError`` if the career has already turned pro.
    """
    if state.pro_career.is_active:
        raise ValueError("Amateur opponents are unavailable after turning pro.")

    randomizer = rng or random.Random()
    tier = current_tier(state)
    boxer = state.boxer
    weight_class = classify_weight(boxer.profile.weight_lbs)

    rating = randomizer.randint(int(tier["opponent_rating_min"]), int(tier["opponent_rating_max"]))
    name = f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}"

    height_inches = max(56, min(84, randomizer.randint(weight_class.avg_height_in - 3, weight_class.avg_height_in + 3)))
    height_ft = height_inches // 12
    height_in = height_inches % 12

    min_weight = max(weight_class.min_lbs, boxer.profile.weight_lbs - 3)
    max_weight = min(weight_class.max_lbs, boxer.profile.weight_lbs + 3)
    if min_weight > max_weight:
        min_weight, max_weight = weight_class.min_lbs, weight_class.max_lbs

    weight_lbs = randomizer.randint(min_weight, max_weight)
    base_stats = build_stats(height_inches=height_inches, weight_lbs=weight_lbs, weight_class=weight_class)
    shift = int(round((rating - _mean_stat(base_stats)) * 0.45))
    adjusted = {k: clamp_stat(v + shift) for k, v in base_stats.to_dict().items()}

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
        stats=Stats.from_dict(adjusted),
        rating=rating,
        record=CareerRecord(wins=wins, losses=losses, draws=randomizer.randint(0, 2), kos=max(0, wins // 2)),
    )


# ---------------------------------------------------------------------------
# Fight result application
# ---------------------------------------------------------------------------

def apply_fight_result(
    state: CareerState,
    opponent: Opponent,
    result: FightResult,
) -> None:
    """Apply an amateur fight result to *state* (record, points, XP, wear).

    Raises ``ValueError`` if the career is already pro.
    """
    if state.pro_career.is_active:
        raise ValueError("Amateur fights are unavailable after turning pro.")

    tier = current_tier(state)
    points_cfg = tier["points"]
    boxer_name = state.boxer.profile.name

    # Record + points
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

    # Experience
    xp_gain = fight_experience_gain(
        stage="amateur", boxer_name=boxer_name,
        opponent_rating=opponent.rating, result=result,
    )
    add_experience_points(state.boxer, xp_gain)

    # Post-fight wear
    impact = calculate_post_fight_impact(
        stage="amateur", boxer_name=boxer_name,
        result=result, rounds_scheduled=int(tier["rounds"]),
    )
    fatigue_gain = adjusted_fatigue_gain(state, impact.fatigue_gain)
    injury_gain = adjusted_injury_risk_gain(state, impact.injury_risk_gain)
    state.boxer.fatigue = min(MAX_FATIGUE, state.boxer.fatigue + fatigue_gain)
    state.boxer.injury_risk = min(MAX_INJURY_RISK, state.boxer.injury_risk + injury_gain)

    # History
    state.history.append(
        FightHistoryEntry(
            opponent_name=opponent.name,
            opponent_rating=opponent.rating,
            result=result,
            stage="amateur",
            purse=0.0,
        )
    )

    # Tier progression
    state.amateur_progress.fights_taken += 1
    state.amateur_progress.tier = _current_tier_by_fights(state.amateur_progress.fights_taken)["name"]


# ---------------------------------------------------------------------------
# Pro readiness
# ---------------------------------------------------------------------------

def pro_readiness_status(state: CareerState) -> ProReadinessStatus:
    """Return a structured readiness snapshot for the pro gate."""
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
    """Return ``True`` when the player meets all pro-gate requirements."""
    return pro_readiness_status(state).is_ready
