import random

from boxing_game.models import CareerRecord, CareerState, FightHistoryEntry, FightResult
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import turn_pro
from boxing_game.modules.retirement_engine import evaluate_retirement, retirement_chance


class _ZeroRng:
    def random(self) -> float:
        return 0.0


def _build_pro_state() -> CareerState:
    boxer = create_boxer(
        name="Retire Me",
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
    )
    state = CareerState(boxer=boxer)
    state.boxer.profile.age = 20
    state.career_months = 60
    state.year = 6
    state.amateur_progress.fights_taken = 12
    state.boxer.amateur_points = 140
    turn_pro(state, rng=random.Random(7))
    return state


def _loss_entry(opponent_name: str = "Tough Opponent") -> FightHistoryEntry:
    result = FightResult(
        winner=opponent_name,
        method="UD",
        rounds_completed=8,
        scorecards=["77-75", "78-74", "79-73"],
        round_log=[],
    )
    return FightHistoryEntry(
        opponent_name=opponent_name,
        opponent_rating=84,
        result=result,
        stage="pro",
        purse=0.0,
    )


def test_forced_retirement_at_age_cap() -> None:
    state = _build_pro_state()
    state.boxer.profile.age = 45

    decision = evaluate_retirement(state, rng=random.Random(1))

    assert decision.is_retired is True
    assert decision.newly_retired is True
    assert decision.forced is True
    assert state.is_retired is True
    assert state.retirement_age == 45
    assert "age cap" in state.retirement_reason


def test_retirement_chance_is_zero_before_age_bands() -> None:
    state = _build_pro_state()
    state.boxer.profile.age = 30

    chance = retirement_chance(state)

    assert chance == 0.0


def test_poor_form_and_health_increase_retirement_chance() -> None:
    poor = _build_pro_state()
    poor.boxer.profile.age = 38
    poor.pro_career.record = CareerRecord(wins=11, losses=13, draws=1, kos=5)
    poor.boxer.injury_risk = 52
    poor.boxer.fatigue = 9
    poor.history = [_loss_entry("Loss A"), _loss_entry("Loss B"), _loss_entry("Loss C")]

    elite = _build_pro_state()
    elite.boxer.profile.age = 38
    elite.pro_career.record = CareerRecord(wins=28, losses=1, draws=0, kos=15)
    elite.boxer.injury_risk = 12
    elite.boxer.fatigue = 2
    for org_name in elite.pro_career.rankings:
        elite.pro_career.rankings[org_name] = 1
    elite.pro_career.lineal_champions[elite.boxer.division] = elite.boxer.profile.name

    poor_chance = retirement_chance(poor)
    elite_chance = retirement_chance(elite)

    assert poor_chance > elite_chance


def test_roll_can_trigger_performance_retirement() -> None:
    state = _build_pro_state()
    state.boxer.profile.age = 39
    state.pro_career.record = CareerRecord(wins=9, losses=12, draws=1, kos=3)
    state.boxer.injury_risk = 55
    state.boxer.fatigue = 10
    state.history = [
        _loss_entry("Loss 1"),
        _loss_entry("Loss 2"),
        _loss_entry("Loss 3"),
        _loss_entry("Loss 4"),
    ]

    decision = evaluate_retirement(state, rng=_ZeroRng())

    assert decision.is_retired is True
    assert decision.newly_retired is True
    assert decision.forced is False
    assert decision.chance > 0.0
    assert state.is_retired is True
