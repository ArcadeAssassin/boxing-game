import random

import pytest

from boxing_game.constants import STARTING_AGE
from boxing_game.models import CareerState
from boxing_game.modules.amateur_circuit import pro_readiness_status, pro_ready
from boxing_game.modules.career_clock import advance_month
from boxing_game.modules.fight_sim_engine import simulate_pro_fight
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import (
    apply_pro_fight_result,
    ensure_rankings,
    generate_pro_opponent,
    offer_purse,
    rankings_snapshot,
    turn_pro,
)
from boxing_game.modules.rating_engine import boxer_overall_rating
from boxing_game.rules_registry import load_rule_set


def _build_pro_ready_state() -> CareerState:
    boxer = create_boxer(
        name="Prospect",
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
    )
    state = CareerState(boxer=boxer)
    state.boxer.profile.age = STARTING_AGE + 3
    state.career_months = 36
    state.year = 4
    state.amateur_progress.fights_taken = 20
    state.amateur_progress.tier = "national"
    state.boxer.amateur_points = 220
    return state


def test_aging_advances_age_after_12_months() -> None:
    boxer = create_boxer(
        name="Young",
        stance="southpaw",
        height_ft=5,
        height_in=8,
        weight_lbs=135,
    )
    state = CareerState(boxer=boxer)

    events = advance_month(state, months=12)

    assert state.boxer.profile.age == STARTING_AGE + 1
    assert state.career_months == 12
    assert state.month == 1
    assert state.year == 2
    assert any("Birthday" in event for event in events)


def test_birthday_applies_stat_changes_after_30() -> None:
    boxer = create_boxer(
        name="Veteran",
        stance="orthodox",
        height_ft=5,
        height_in=11,
        weight_lbs=154,
    )
    state = CareerState(boxer=boxer)
    state.boxer.profile.age = 29
    state.career_months = 11
    speed_before = state.boxer.stats.speed
    iq_before = state.boxer.stats.ring_iq

    advance_month(state, months=1)

    assert state.boxer.profile.age == 30
    assert state.boxer.stats.speed == speed_before - 1
    assert state.boxer.stats.ring_iq == iq_before + 1


def test_turn_pro_and_pro_fight_updates_finances_and_history() -> None:
    rng = random.Random(11)
    state = _build_pro_ready_state()

    details = turn_pro(state, rng=rng)
    assert state.pro_career.is_active is True
    assert details["promoter"]
    assert details["organization_focus"]

    opponent = generate_pro_opponent(state, rng=rng)
    purse = offer_purse(state, opponent, rng=rng)
    result = simulate_pro_fight(state.boxer, opponent, rounds=6, rng=rng)
    new_rank = apply_pro_fight_result(state, opponent, result, purse)

    pro_total = (
        state.pro_career.record.wins
        + state.pro_career.record.losses
        + state.pro_career.record.draws
    )

    assert pro_total == 1
    assert len(state.history) == 1
    assert state.history[0].stage == "pro"
    assert state.pro_career.purse_balance > 0
    assert state.pro_career.total_earnings >= state.pro_career.purse_balance
    focus = state.pro_career.organization_focus
    slots = next(
        int(item["ranking_slots"])
        for item in load_rule_set("pro_career")["organizations"]
        if item["name"] == focus
    )
    assert new_rank is None or 1 <= new_rank <= slots


def test_advance_month_rejects_negative_value() -> None:
    state = _build_pro_ready_state()
    with pytest.raises(ValueError, match="Months must be >= 0"):
        advance_month(state, months=-1)


def test_pro_ready_requires_min_age_even_if_points_and_fights_met() -> None:
    state = _build_pro_ready_state()
    state.boxer.profile.age = STARTING_AGE + 2

    assert pro_ready(state) is False


def test_pro_readiness_status_reports_progress() -> None:
    state = _build_pro_ready_state()
    state.boxer.profile.age = STARTING_AGE + 2
    state.amateur_progress.fights_taken = 12
    state.boxer.amateur_points = 111

    status = pro_readiness_status(state)

    assert status.current_age == STARTING_AGE + 2
    assert status.current_fights == 12
    assert status.current_points == 111
    assert status.min_age == 19
    assert status.min_fights == 18
    assert status.min_points == 170
    assert status.is_ready is False


def test_ensure_rankings_backfills_missing_organizations() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(3))
    state.pro_career.rankings = {"WBC": 10}

    ensure_rankings(state)
    org_names = [item["name"] for item in load_rule_set("pro_career")["organizations"]]

    for org_name in org_names:
        assert org_name in state.pro_career.rankings


def test_purse_breakdown_has_total_expenses() -> None:
    rng = random.Random(17)
    state = _build_pro_ready_state()
    turn_pro(state, rng=rng)
    opponent = generate_pro_opponent(state, rng=rng)
    purse = offer_purse(state, opponent, rng=rng)

    summed = (
        purse["manager_cut"]
        + purse["trainer_cut"]
        + purse["camp_cost"]
        + purse["commission_cut"]
        + purse["sanction_fee"]
    )
    assert purse["total_expenses"] == pytest.approx(summed, rel=0.0, abs=0.02)


def test_boxer_overall_rating_stays_in_bounds() -> None:
    state = _build_pro_ready_state()
    rating = boxer_overall_rating(state.boxer, stage="amateur")
    assert 20 <= rating <= 99


def test_rankings_snapshot_requires_pro_state() -> None:
    boxer = create_boxer(
        name="No Pro",
        stance="orthodox",
        height_ft=5,
        height_in=11,
        weight_lbs=160,
    )
    state = CareerState(boxer=boxer)
    with pytest.raises(ValueError, match="available after turning pro"):
        rankings_snapshot(state, "WBC")


def test_rankings_snapshot_contains_player_row() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(31))
    state.pro_career.rankings["WBC"] = 28

    rows = rankings_snapshot(state, "WBC", top_n=15)
    player_rows = [row for row in rows if row.is_player]

    assert len(player_rows) == 1
    assert player_rows[0].name == state.boxer.profile.name
