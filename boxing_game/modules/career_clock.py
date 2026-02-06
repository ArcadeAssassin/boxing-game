"""Calendar and age progression.

Advances the career month-by-month, triggering birthday stat changes
when a full year elapses.  Aging deltas respect each boxer's personal
aging profile and any sports-science staff upgrades.
"""

from __future__ import annotations

from boxing_game.models import CareerState, Stats
from boxing_game.modules.pro_spending import (
    age_decline_reduction_factor,
    age_iq_growth_bonus_factor,
)
from boxing_game.rules_registry import load_rule_set
from boxing_game.utils import clamp_int


def _birthday_stat_changes(state: CareerState) -> list[str]:
    """Apply age-bracket stat deltas on the boxer's birthday.

    Returns a list of human-readable change descriptions.
    """
    rules = load_rule_set("aging_model")
    limits = rules["stat_limits"]
    min_stat = int(limits["min"])
    max_stat = int(limits["max"])

    age = state.boxer.profile.age
    deltas: dict[str, int] = {}
    for bracket in rules["age_brackets"]:
        if int(bracket["min_age"]) <= age <= int(bracket["max_age"]):
            deltas = {str(k): int(v) for k, v in bracket["stat_deltas"].items()}
            break

    if not deltas:
        return []

    profile = state.boxer.aging_profile
    sports_science_decline = age_decline_reduction_factor(state)
    sports_science_iq = age_iq_growth_bonus_factor(state)
    decline_accel_per_year = float(rules.get("decline_acceleration_per_year", 0.04))

    stats_map = state.boxer.stats.to_dict()
    logs: list[str] = []

    for stat_name, delta in deltas.items():
        if stat_name not in stats_map:
            continue

        adjusted_delta = _resolve_delta(
            delta,
            stat_name=stat_name,
            age=age,
            profile=profile,
            decline_accel_per_year=decline_accel_per_year,
            sports_science_decline=sports_science_decline,
            sports_science_iq=sports_science_iq,
        )

        old_value = stats_map[stat_name]
        new_value = clamp_int(old_value + adjusted_delta, min_stat, max_stat)
        if new_value != old_value:
            stats_map[stat_name] = new_value
            applied = new_value - old_value
            label = f"+{applied}" if applied > 0 else str(applied)
            logs.append(f"{stat_name} {old_value}->{new_value} ({label})")

    if logs:
        state.boxer.stats = Stats.from_dict(stats_map)
    return logs


def _resolve_delta(
    delta: int,
    *,
    stat_name: str,
    age: int,
    profile: object,
    decline_accel_per_year: float,
    sports_science_decline: float,
    sports_science_iq: float,
) -> int:
    """Compute the effective delta for a single stat on a birthday."""
    # Decline deltas are suppressed before the boxer's personal onset age.
    if delta < 0:
        if age < profile.decline_onset_age:  # type: ignore[union-attr]
            return 0
        years_into_decline = max(0, age - profile.decline_onset_age)  # type: ignore[union-attr]
        age_accel = 1.0 + (years_into_decline * decline_accel_per_year)
        decline_factor = profile.decline_severity * age_accel * sports_science_decline  # type: ignore[union-attr]
        scaled = int(round(delta * decline_factor))
        return scaled if scaled != 0 else -1

    # Ring-IQ growth is boosted by profile factor + sports science.
    if delta > 0 and stat_name == "ring_iq":
        iq_factor = profile.iq_growth_factor * sports_science_iq  # type: ignore[union-attr]
        return max(1, int(round(delta * iq_factor)))

    return int(delta)


def advance_month(state: CareerState, months: int = 1) -> list[str]:
    """Advance the career clock by *months*, returning birthday events.

    Raises ``ValueError`` for negative month values.
    """
    if months < 0:
        raise ValueError("Months must be >= 0.")
    if months == 0:
        return []

    events: list[str] = []
    for _ in range(months):
        state.month += 1
        if state.month > 12:
            state.month = 1
            state.year += 1

        state.career_months += 1
        if state.career_months % 12 == 0:
            state.boxer.profile.age += 1
            changes = _birthday_stat_changes(state)
            if changes:
                events.append(
                    f"Birthday: now age {state.boxer.profile.age}. Age effects: {', '.join(changes)}."
                )
            else:
                events.append(f"Birthday: now age {state.boxer.profile.age}.")
    return events
