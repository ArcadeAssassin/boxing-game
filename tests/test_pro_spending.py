import random

import pytest

from boxing_game.constants import STARTING_AGE
from boxing_game.models import CareerState
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import turn_pro
from boxing_game.modules.pro_spending import (
    age_decline_reduction_factor,
    age_iq_growth_bonus_factor,
    adjusted_fatigue_gain,
    adjusted_injury_risk_gain,
    apply_rest_month,
    apply_standard_training,
    list_staff_upgrade_options,
    medical_recovery,
    purchase_staff_upgrade,
    special_training_camp,
)


def _build_pro_state() -> CareerState:
    boxer = create_boxer(
        name="Money Boxer",
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
    )
    state = CareerState(boxer=boxer)
    state.boxer.profile.age = STARTING_AGE + 3
    state.career_months = 36
    state.year = 4
    state.amateur_progress.fights_taken = 14
    state.boxer.amateur_points = 130
    turn_pro(state, rng=random.Random(77))
    state.pro_career.purse_balance = 20000.0
    return state


def test_special_training_camp_spends_money_and_boosts_stats() -> None:
    state = _build_pro_state()
    speed_before = state.boxer.stats.speed
    balance_before = state.pro_career.purse_balance
    fatigue_before = state.boxer.fatigue
    injury_before = state.boxer.injury_risk

    details = special_training_camp(state, "speed")

    assert details["cost"] > 0
    assert state.pro_career.purse_balance == pytest.approx(
        balance_before - float(details["cost"]), rel=0.0, abs=0.01
    )
    assert state.boxer.stats.speed > speed_before
    assert state.boxer.fatigue >= fatigue_before
    assert state.boxer.injury_risk >= injury_before


def test_medical_recovery_spends_money_and_reduces_wear() -> None:
    state = _build_pro_state()
    state.boxer.fatigue = 10
    state.boxer.injury_risk = 30
    balance_before = state.pro_career.purse_balance

    details = medical_recovery(state)

    assert details["cost"] > 0
    assert details["fatigue_reduced"] > 0
    assert details["injury_risk_reduced"] > 0
    assert state.pro_career.purse_balance == pytest.approx(
        balance_before - float(details["cost"]), rel=0.0, abs=0.01
    )
    assert state.boxer.fatigue < 10
    assert state.boxer.injury_risk < 30


def test_elite_coach_adds_passive_training_bonus() -> None:
    state = _build_pro_state()
    before_power = state.boxer.stats.power
    purchase_staff_upgrade(state, "elite_coach")

    details = apply_standard_training(state, "power")

    assert details["coach_bonus"] >= 1
    assert state.boxer.stats.power - before_power >= 3


def test_nutritionist_reduces_wear_and_improves_rest() -> None:
    state = _build_pro_state()
    purchase_staff_upgrade(state, "nutritionist")

    assert adjusted_fatigue_gain(state, 1) == 0
    assert adjusted_injury_risk_gain(state, 2) == 1

    state.boxer.fatigue = 8
    state.boxer.injury_risk = 12
    details = apply_rest_month(state)

    assert details["fatigue_reduced"] == 4
    assert details["injury_risk_reduced"] == 4


def test_special_training_camp_rejects_low_balance() -> None:
    state = _build_pro_state()
    state.pro_career.purse_balance = 100.0

    with pytest.raises(ValueError, match="Insufficient purse balance"):
        special_training_camp(state, "speed")


def test_staff_options_include_sports_science_upgrade() -> None:
    state = _build_pro_state()

    options = {option.key: option for option in list_staff_upgrade_options(state)}

    assert "sports_science" in options
    assert options["sports_science"].next_cost is not None


def test_sports_science_modifies_aging_factors() -> None:
    state = _build_pro_state()
    state.pro_career.purse_balance = 30000.0

    base_decline = age_decline_reduction_factor(state)
    base_iq = age_iq_growth_bonus_factor(state)

    purchase_staff_upgrade(state, "sports_science")
    purchase_staff_upgrade(state, "sports_science")
    purchase_staff_upgrade(state, "sports_science")

    improved_decline = age_decline_reduction_factor(state)
    improved_iq = age_iq_growth_bonus_factor(state)

    assert improved_decline < base_decline
    assert improved_iq > base_iq
    assert improved_decline == pytest.approx(0.76, rel=0.0, abs=0.0001)
    assert improved_iq == pytest.approx(1.18, rel=0.0, abs=0.0001)
