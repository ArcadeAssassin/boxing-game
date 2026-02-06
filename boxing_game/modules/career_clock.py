from __future__ import annotations

from boxing_game.models import CareerState, Stats
from boxing_game.rules_registry import load_rule_set


def _clamp_stat(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _birthday_stat_changes(state: CareerState) -> list[str]:
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

    stats_map = state.boxer.stats.to_dict()
    logs: list[str] = []
    for stat_name, delta in deltas.items():
        if stat_name not in stats_map:
            continue
        old_value = stats_map[stat_name]
        new_value = _clamp_stat(old_value + delta, min_stat, max_stat)
        if new_value != old_value:
            stats_map[stat_name] = new_value
            delta_label = f"+{delta}" if delta > 0 else str(delta)
            logs.append(f"{stat_name} {old_value}->{new_value} ({delta_label})")

    if logs:
        state.boxer.stats = Stats.from_dict(stats_map)
    return logs


def advance_month(state: CareerState, months: int = 1) -> list[str]:
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
