import random

from boxing_game.constants import STARTING_AGE
from boxing_game.models import CareerState
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import turn_pro
from boxing_game.modules.world_sim import simulate_world_month


def _build_pro_state() -> CareerState:
    boxer = create_boxer(
        name="World Sim Player",
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
    )
    state = CareerState(boxer=boxer)
    state.boxer.profile.age = STARTING_AGE + 3
    state.career_months = 36
    state.year = 4
    state.amateur_progress.fights_taken = 12
    state.boxer.amateur_points = 130
    turn_pro(state, rng=random.Random(13))
    return state


def test_world_sim_fills_vacant_organization_titles() -> None:
    state = _build_pro_state()
    division = state.boxer.division
    for org_name in ["WBC", "WBA", "IBF", "WBO"]:
        state.pro_career.organization_champions.setdefault(org_name, {})[division] = None
        state.pro_career.organization_defenses.setdefault(org_name, {})[division] = 0

    events = simulate_world_month(state, rng=random.Random(14))

    assert len(events) >= 4
    for org_name in ["WBC", "WBA", "IBF", "WBO"]:
        champion = state.pro_career.organization_champions[org_name][division]
        assert champion is not None
    assert state.pro_career.last_world_news


def test_world_sim_does_not_apply_rank_drift_in_player_fight_month() -> None:
    state = _build_pro_state()
    for org_name in state.pro_career.rankings:
        state.pro_career.rankings[org_name] = 10
    state.pro_career.last_player_fight_month = state.career_months

    simulate_world_month(state, rng=random.Random(77))

    for org_name in state.pro_career.rankings:
        assert state.pro_career.rankings[org_name] == 10
