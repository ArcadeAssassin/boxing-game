import random

import pytest

from boxing_game.models import CareerState
from boxing_game.modules.amateur_circuit import apply_fight_result, generate_opponent
from boxing_game.modules.fight_sim_engine import simulate_amateur_fight
from boxing_game.modules.player_profile import create_boxer


def test_amateur_fight_updates_record_and_history() -> None:
    rng = random.Random(42)
    boxer = create_boxer(
        name="Flow Tester",
        stance="orthodox",
        height_ft=6,
        height_in=0,
        weight_lbs=160,
    )
    state = CareerState(boxer=boxer)

    opponent = generate_opponent(state, rng=rng)
    result = simulate_amateur_fight(state.boxer, opponent, rounds=3, rng=rng)
    apply_fight_result(state, opponent, result)

    total_bouts = (
        state.boxer.record.wins + state.boxer.record.losses + state.boxer.record.draws
    )
    assert total_bouts == 1
    assert state.amateur_progress.fights_taken == 1
    assert len(state.history) == 1
    assert state.history[0].stage == "amateur"


def test_generate_opponent_rejects_pro_state() -> None:
    boxer = create_boxer(
        name="No Amateur",
        stance="orthodox",
        height_ft=6,
        height_in=1,
        weight_lbs=175,
    )
    state = CareerState(boxer=boxer)
    state.pro_career.is_active = True

    with pytest.raises(ValueError, match="Amateur opponents are unavailable"):
        generate_opponent(state, rng=random.Random(1))
