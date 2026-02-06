import random

import pytest

from boxing_game.models import CareerState, FightResult
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
    assert state.boxer.experience_points > 0


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


def test_simulate_amateur_fight_rejects_invalid_round_count() -> None:
    rng = random.Random(7)
    boxer = create_boxer(
        name="Round Guard",
        stance="orthodox",
        height_ft=5,
        height_in=11,
        weight_lbs=154,
    )
    state = CareerState(boxer=boxer)
    opponent = generate_opponent(state, rng=rng)

    with pytest.raises(ValueError, match="Rounds must be >= 1"):
        simulate_amateur_fight(state.boxer, opponent, rounds=0, rng=rng)


def test_amateur_result_type_changes_post_fight_wear() -> None:
    rng = random.Random(101)
    boxer = create_boxer(
        name="Outcome Wear",
        stance="orthodox",
        height_ft=5,
        height_in=11,
        weight_lbs=154,
    )
    opponent_state = CareerState(boxer=boxer)
    opponent = generate_opponent(opponent_state, rng=rng)

    win_state = CareerState(
        boxer=create_boxer(
            name="Outcome Wear",
            stance="orthodox",
            height_ft=5,
            height_in=11,
            weight_lbs=154,
        )
    )
    loss_state = CareerState(
        boxer=create_boxer(
            name="Outcome Wear",
            stance="orthodox",
            height_ft=5,
            height_in=11,
            weight_lbs=154,
        )
    )

    win_result = FightResult(
        winner=win_state.boxer.profile.name,
        method="UD",
        rounds_completed=3,
        scorecards=["29-28", "29-28", "30-27"],
        round_log=[],
    )
    loss_result = FightResult(
        winner=opponent.name,
        method="TKO",
        rounds_completed=1,
        scorecards=[],
        round_log=[],
    )

    apply_fight_result(win_state, opponent, win_result)
    apply_fight_result(loss_state, opponent, loss_result)

    assert loss_state.boxer.fatigue > win_state.boxer.fatigue
    assert loss_state.boxer.injury_risk > win_state.boxer.injury_risk
