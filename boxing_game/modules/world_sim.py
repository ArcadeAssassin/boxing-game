from __future__ import annotations

import random

from boxing_game.models import CareerState
from boxing_game.modules.pro_career import (
    _organization_names,
    _ranking_slots,
    ensure_organization_titles,
    ensure_rankings,
    organization_division_champion,
)


def _clamp_rank(value: int, org_name: str) -> int:
    return max(1, min(_ranking_slots(org_name), int(value)))


def _seed_name(state: CareerState, label: str, randomizer: random.Random) -> str:
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
) -> list[str]:
    boxer_name = state.boxer.profile.name
    events: list[str] = []
    for org_name in _organization_names():
        champion = organization_division_champion(state, org_name, division)
        champions = state.pro_career.organization_champions[org_name]
        defenses = state.pro_career.organization_defenses[org_name]

        if champion is None:
            challenger_a = _seed_name(state, f"{org_name}:{division}:vacA", randomizer)
            challenger_b = _seed_name(state, f"{org_name}:{division}:vacB", randomizer)
            winner = challenger_a if randomizer.random() < 0.52 else challenger_b
            champions[division] = winner
            defenses[division] = 0
            events.append(f"{org_name}: {winner} won the vacant {division} title.")
            continue

        # Player title defenses happen only in player-driven fights.
        if champion == boxer_name:
            continue

        if randomizer.random() < 0.3:
            challenger = _seed_name(state, f"{org_name}:{division}:ch", randomizer)
            upset_chance = 0.18
            if randomizer.random() < upset_chance:
                champions[division] = challenger
                defenses[division] = 0
                events.append(
                    f"{org_name}: {challenger} dethroned {champion} at {division}."
                )
            else:
                defenses[division] = defenses.get(division, 0) + 1
                if randomizer.random() < 0.65:
                    events.append(
                        f"{org_name}: {champion} defended {division} title "
                        f"(D{defenses[division]})."
                    )
    return events


def _simulate_player_rank_drift(state: CareerState, randomizer: random.Random) -> list[str]:
    events: list[str] = []
    boxer_name = state.boxer.profile.name
    months_since_fight = max(0, state.career_months - state.pro_career.last_player_fight_month)
    if months_since_fight <= 0:
        return events

    for org_name in _organization_names():
        champion = organization_division_champion(state, org_name, state.boxer.division)
        if champion == boxer_name:
            state.pro_career.rankings[org_name] = 1
            continue

        old_rank = state.pro_career.rankings.get(org_name)
        if old_rank is None:
            continue

        drift_up = 0
        drift_down = 0

        if months_since_fight >= 2 and randomizer.random() < min(0.42, 0.12 * months_since_fight):
            drift_up += randomizer.randint(1, 2)
        if randomizer.random() < 0.1:
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
    randomizer = rng or random.Random()

    division = state.boxer.division
    events: list[str] = []
    events.extend(_simulate_titles_for_division(state, division, randomizer))
    events.extend(_simulate_player_rank_drift(state, randomizer))

    state.pro_career.last_world_news = events[-12:]
    return events
