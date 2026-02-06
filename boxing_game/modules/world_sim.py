from __future__ import annotations

import random

from boxing_game.models import CareerState
from boxing_game.modules.pro_career import (
    division_names,
    ensure_organization_titles,
    ensure_rankings,
    organization_division_champion,
    organization_names,
    ranking_slots,
)
from boxing_game.rules_registry import load_rule_set


def _clamp_rank(value: int, org_name: str) -> int:
    return max(1, min(ranking_slots(org_name), int(value)))


def _clamp_float(value: object, default: float, *, low: float = 0.0, high: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(low, min(high, numeric))


def _world_policy() -> dict[str, float | int | bool]:
    rules = load_rule_set("pro_career")
    raw = rules.get("world_simulation", {})
    if not isinstance(raw, dict):
        raw = {}
    return {
        "simulate_all_divisions": bool(raw.get("simulate_all_divisions", True)),
        "title_fight_probability_per_org": _clamp_float(
            raw.get("title_fight_probability_per_org", 0.3),
            0.3,
        ),
        "title_upset_probability": _clamp_float(
            raw.get("title_upset_probability", 0.18),
            0.18,
        ),
        "title_defense_news_probability": _clamp_float(
            raw.get("title_defense_news_probability", 0.65),
            0.65,
        ),
        "max_news_items_per_month": max(1, int(raw.get("max_news_items_per_month", 20))),
        "rank_drift_up_probability_per_idle_month": _clamp_float(
            raw.get("rank_drift_up_probability_per_idle_month", 0.12),
            0.12,
        ),
        "rank_drift_up_probability_cap": _clamp_float(
            raw.get("rank_drift_up_probability_cap", 0.42),
            0.42,
        ),
        "rank_drift_down_probability": _clamp_float(
            raw.get("rank_drift_down_probability", 0.1),
            0.1,
        ),
        "rank_drift_up_step_min": max(1, int(raw.get("rank_drift_up_step_min", 1))),
        "rank_drift_up_step_max": max(1, int(raw.get("rank_drift_up_step_max", 2))),
    }


def _seed_name(state: CareerState, label: str) -> str:
    first_names = ["Luis", "Kenji", "Marco", "Andre", "Devin", "Isaac", "Raul", "Tyson"]
    last_names = ["Santos", "Mori", "Grant", "Rivera", "Ramos", "Nguyen", "Mills", "Carter"]
    seeded = random.Random(
        f"{state.boxer.profile.name}:{state.career_months}:{state.year}:{state.month}:{label}"
    )
    return f"{seeded.choice(first_names)} {seeded.choice(last_names)}"


def _simulate_titles_for_division(
    state: CareerState,
    division: str,
    randomizer: random.Random,
    policy: dict[str, float | int | bool],
) -> list[str]:
    boxer_name = state.boxer.profile.name
    events: list[str] = []
    title_fight_probability = float(policy["title_fight_probability_per_org"])
    upset_probability = float(policy["title_upset_probability"])
    defense_news_probability = float(policy["title_defense_news_probability"])

    for org_name in organization_names():
        champion = organization_division_champion(state, org_name, division)
        champions = state.pro_career.organization_champions[org_name]
        defenses = state.pro_career.organization_defenses[org_name]

        if champion is None:
            challenger_a = _seed_name(state, f"{org_name}:{division}:vacA")
            challenger_b = _seed_name(state, f"{org_name}:{division}:vacB")
            winner = challenger_a if randomizer.random() < 0.52 else challenger_b
            champions[division] = winner
            defenses[division] = 0
            events.append(f"{org_name}: {winner} won the vacant {division} title.")
            continue

        if champion == boxer_name and division == state.boxer.division:
            # Player title actions happen in player-driven fights.
            continue

        if randomizer.random() < title_fight_probability:
            challenger = _seed_name(state, f"{org_name}:{division}:ch")
            if randomizer.random() < upset_probability:
                champions[division] = challenger
                defenses[division] = 0
                events.append(f"{org_name}: {challenger} dethroned {champion} at {division}.")
            else:
                defenses[division] = defenses.get(division, 0) + 1
                if randomizer.random() < defense_news_probability:
                    events.append(
                        f"{org_name}: {champion} defended {division} title (D{defenses[division]})."
                    )
    return events


def _simulate_player_rank_drift(
    state: CareerState,
    randomizer: random.Random,
    policy: dict[str, float | int | bool],
) -> list[str]:
    events: list[str] = []
    boxer_name = state.boxer.profile.name
    months_since_fight = max(0, state.career_months - state.pro_career.last_player_fight_month)
    if months_since_fight <= 0:
        return events

    drift_up_probability = min(
        float(policy["rank_drift_up_probability_cap"]),
        float(policy["rank_drift_up_probability_per_idle_month"]) * months_since_fight,
    )
    drift_down_probability = float(policy["rank_drift_down_probability"])
    drift_up_step_min = int(policy["rank_drift_up_step_min"])
    drift_up_step_max = int(policy["rank_drift_up_step_max"])
    if drift_up_step_max < drift_up_step_min:
        drift_up_step_max = drift_up_step_min

    for org_name in organization_names():
        champion = organization_division_champion(state, org_name, state.boxer.division)
        if champion == boxer_name:
            state.pro_career.rankings[org_name] = 1
            continue

        old_rank = state.pro_career.rankings.get(org_name)
        if old_rank is None:
            continue

        drift_up = 0
        drift_down = 0

        if months_since_fight >= 2 and randomizer.random() < drift_up_probability:
            drift_up += randomizer.randint(drift_up_step_min, drift_up_step_max)
        if randomizer.random() < drift_down_probability:
            drift_down += 1

        new_rank = _clamp_rank(old_rank + drift_up - drift_down, org_name)
        if new_rank != old_rank:
            state.pro_career.rankings[org_name] = new_rank
            events.append(f"{org_name}: ranking shifted #{old_rank} -> #{new_rank}.")
    return events


def simulate_world_month(
    state: CareerState,
    rng: random.Random | None = None,
) -> list[str]:
    if not state.pro_career.is_active:
        return []

    ensure_rankings(state)
    ensure_organization_titles(state)
    policy = _world_policy()
    randomizer = rng or random.Random()

    if bool(policy["simulate_all_divisions"]):
        divisions = division_names()
    else:
        divisions = [state.boxer.division]

    events: list[str] = []
    for division in divisions:
        events.extend(_simulate_titles_for_division(state, division, randomizer, policy))
        if len(events) >= int(policy["max_news_items_per_month"]):
            break

    events.extend(_simulate_player_rank_drift(state, randomizer, policy))
    events = events[: int(policy["max_news_items_per_month"])]

    state.pro_career.last_world_news = events[-12:]
    return events
