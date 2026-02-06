"""In-game retirement system.

Evaluates retirement probability each month based on age, performance,
injury, fatigue, and championship protection.  Configurable via
``rules/retirement_model.json``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from boxing_game.models import CareerState
from boxing_game.rules_registry import load_rule_set
from boxing_game.utils import clamp_float


@dataclass(frozen=True)
class RetirementEvaluation:
    """Result of a monthly retirement check."""

    is_retired: bool
    newly_retired: bool
    forced: bool
    chance: float
    roll: float | None
    reason: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rules() -> dict:
    return load_rule_set("retirement_model")


def _base_age_chance(age: int) -> float:
    for band in _rules()["age_bands"]:
        if int(band["min_age"]) <= age <= int(band["max_age"]):
            return float(band["base_chance"])
    return 0.0


def _active_record(state: CareerState) -> tuple[int, int, int, int, float]:
    record = state.pro_career.record if state.pro_career.is_active else state.boxer.record
    wins, losses, draws = int(record.wins), int(record.losses), int(record.draws)
    total = wins + losses + draws
    win_rate = 0.0 if total == 0 else (wins / total)
    return wins, losses, draws, total, win_rate


def _stage_history(state: CareerState) -> list:
    stage = "pro" if state.pro_career.is_active else "amateur"
    return [entry for entry in state.history if entry.stage == stage]


def _recent_loss_streak(state: CareerState, window: int) -> int:
    boxer_name = state.boxer.profile.name
    streak = 0
    for entry in reversed(_stage_history(state)[-window:]):
        winner = entry.result.winner
        if winner == boxer_name or winner == "Draw":
            break
        streak += 1
    return streak


def _recent_no_win(state: CareerState, window: int) -> bool:
    boxer_name = state.boxer.profile.name
    recent = _stage_history(state)[-window:]
    if not recent:
        return False
    return all(entry.result.winner != boxer_name for entry in recent)


def _has_lineal_title(state: CareerState) -> bool:
    boxer_name = state.boxer.profile.name
    return any(champion == boxer_name for champion in state.pro_career.lineal_champions.values())


def _best_rank(state: CareerState) -> int | None:
    ranks = [rank for rank in state.pro_career.rankings.values() if rank is not None]
    if not ranks:
        return None
    return min(int(rank) for rank in ranks)


# ---------------------------------------------------------------------------
# Probability calculation
# ---------------------------------------------------------------------------

def retirement_chance(state: CareerState) -> float:
    """Return the probability that the boxer retires this month.

    Accounts for age bands, performance modifiers, injury/fatigue, and
    championship protections.
    """
    if state.is_retired:
        return 1.0

    age = int(state.boxer.profile.age)
    rules = _rules()
    hard_age_cap = int(rules["hard_age_cap"])
    if age >= hard_age_cap:
        return 1.0

    chance = _base_age_chance(age)
    if chance <= 0.0:
        return 0.0

    chance = _apply_performance_modifiers(state, chance, rules)
    chance = _apply_protection_modifiers(state, chance, rules)

    bounds = rules["chance_bounds"]
    return clamp_float(chance, float(bounds["min"]), float(bounds["max"]))


def _apply_performance_modifiers(
    state: CareerState,
    chance: float,
    rules: dict,
) -> float:
    """Adjust retirement chance based on win-rate, loss streaks, and health."""
    perf = rules["performance"]
    _, _, _, total_fights, win_rate = _active_record(state)

    if total_fights >= int(perf["sample_fights_min"]):
        if win_rate < float(perf["win_rate_low"]):
            chance += float(perf["mod_low"])
        elif win_rate < float(perf["win_rate_mid"]):
            chance += float(perf["mod_mid"])
        elif win_rate > float(perf["win_rate_elite"]):
            chance += float(perf["mod_elite"])
        elif win_rate > float(perf["win_rate_high"]):
            chance += float(perf["mod_high"])

    recent_window = int(perf["recent_window"])
    loss_streak = _recent_loss_streak(state, recent_window)
    if loss_streak > 1:
        chance += float(perf["recent_loss_streak_step"]) * (loss_streak - 1)
    if _recent_no_win(state, recent_window):
        chance += float(perf["recent_no_win_bonus"])

    injury_threshold = int(perf["injury_threshold"])
    if state.boxer.injury_risk > injury_threshold:
        chance += (state.boxer.injury_risk - injury_threshold) * float(perf["injury_per_point"])

    fatigue_threshold = int(perf["fatigue_threshold"])
    if state.boxer.fatigue > fatigue_threshold:
        chance += (state.boxer.fatigue - fatigue_threshold) * float(perf["fatigue_per_point"])

    return chance


def _apply_protection_modifiers(
    state: CareerState,
    chance: float,
    rules: dict,
) -> float:
    """Reduce retirement chance for champions and early-career fighters."""
    if not state.pro_career.is_active:
        return chance

    perf = rules["performance"]
    if _has_lineal_title(state):
        chance -= float(perf["champion_protection"])

    best_rank = _best_rank(state)
    rank_cutoff = int(perf["top_rank_cutoff"])
    if best_rank is not None and best_rank <= rank_cutoff:
        steps = rank_cutoff - best_rank + 1
        chance -= steps * float(perf["top_rank_protection_per_step"])

    pro_record = state.pro_career.record
    pro_total = int(pro_record.wins + pro_record.losses + pro_record.draws)
    if pro_total <= int(perf["early_career_fights"]) and int(state.boxer.profile.age) < 35:
        chance -= float(perf["early_career_protection"])

    return chance


# ---------------------------------------------------------------------------
# Retirement reason formatting
# ---------------------------------------------------------------------------

def _retirement_reason(state: CareerState, *, forced: bool) -> str:
    age = state.boxer.profile.age
    if forced:
        hard_age_cap = int(_rules()["hard_age_cap"])
        return f"Retired at age {age} after reaching the age cap ({hard_age_cap})."

    if state.pro_career.is_active:
        record = state.pro_career.record
        return (
            f"Retired at age {age} after evaluating health, form, and performance. "
            f"Final pro record: {record.wins}-{record.losses}-{record.draws}."
        )

    record = state.boxer.record
    return (
        f"Retired at age {age} after evaluating health and progression. "
        f"Final amateur record: {record.wins}-{record.losses}-{record.draws}."
    )


# ---------------------------------------------------------------------------
# Public evaluation
# ---------------------------------------------------------------------------

def evaluate_retirement(
    state: CareerState,
    *,
    rng: random.Random | None = None,
) -> RetirementEvaluation:
    """Evaluate whether *state*'s boxer retires this month.

    Returns a ``RetirementEvaluation`` indicating the outcome.  Side
    effect: mutates ``state`` to mark the boxer as retired when
    the roll triggers retirement.
    """
    if state.is_retired:
        return RetirementEvaluation(
            is_retired=True, newly_retired=False, forced=False,
            chance=1.0, roll=None, reason=state.retirement_reason,
        )

    age = int(state.boxer.profile.age)
    hard_age_cap = int(_rules()["hard_age_cap"])
    if age >= hard_age_cap:
        reason = _retirement_reason(state, forced=True)
        state.is_retired = True
        state.retirement_age = age
        state.retirement_reason = reason
        return RetirementEvaluation(
            is_retired=True, newly_retired=True, forced=True,
            chance=1.0, roll=None, reason=reason,
        )

    chance = retirement_chance(state)
    if chance <= 0.0:
        return RetirementEvaluation(
            is_retired=False, newly_retired=False, forced=False,
            chance=0.0, roll=None, reason="",
        )

    randomizer = rng or random.Random()
    roll = randomizer.random()
    if roll < chance:
        reason = _retirement_reason(state, forced=False)
        state.is_retired = True
        state.retirement_age = age
        state.retirement_reason = reason
        return RetirementEvaluation(
            is_retired=True, newly_retired=True, forced=False,
            chance=chance, roll=roll, reason=reason,
        )

    return RetirementEvaluation(
        is_retired=False, newly_retired=False, forced=False,
        chance=chance, roll=roll, reason="",
    )
