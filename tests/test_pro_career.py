import random

import pytest

from boxing_game.constants import STARTING_AGE
from boxing_game.models import CareerRecord, CareerState, FightResult, Opponent, Stats
from boxing_game.modules.amateur_circuit import pro_readiness_status, pro_ready
from boxing_game.modules.career_clock import advance_month
from boxing_game.modules.fight_sim_engine import simulate_pro_fight
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import (
    apply_pro_fight_result,
    change_division,
    determine_sanctioning_bodies,
    ensure_rankings,
    generate_pro_opponent,
    offer_purse,
    player_lineal_division,
    pound_for_pound_snapshot,
    rankings_snapshot,
    turn_pro,
)
from boxing_game.modules.pro_spending import purchase_staff_upgrade
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
    state.boxer.aging_profile.peak_age = 28
    state.boxer.aging_profile.decline_onset_age = 30
    state.boxer.aging_profile.decline_severity = 1.0
    state.boxer.aging_profile.iq_growth_factor = 1.0
    speed_before = state.boxer.stats.speed
    iq_before = state.boxer.stats.ring_iq

    advance_month(state, months=1)

    assert state.boxer.profile.age == 30
    assert state.boxer.stats.speed == speed_before - 1
    assert state.boxer.stats.ring_iq == iq_before + 1


def test_birthday_suppresses_decline_before_profile_onset() -> None:
    boxer = create_boxer(
        name="Late Decline",
        stance="orthodox",
        height_ft=6,
        height_in=0,
        weight_lbs=168,
    )
    state = CareerState(boxer=boxer)
    state.boxer.profile.age = 29
    state.career_months = 11
    state.boxer.aging_profile.peak_age = 32
    state.boxer.aging_profile.decline_onset_age = 35
    state.boxer.aging_profile.decline_severity = 1.0
    state.boxer.aging_profile.iq_growth_factor = 1.0
    speed_before = state.boxer.stats.speed
    iq_before = state.boxer.stats.ring_iq

    advance_month(state, months=1)

    assert state.boxer.profile.age == 30
    assert state.boxer.stats.speed == speed_before
    assert state.boxer.stats.ring_iq == iq_before + 1


def test_sports_science_reduces_age_decline_delta() -> None:
    base = _build_pro_ready_state()
    improved = _build_pro_ready_state()
    turn_pro(base, rng=random.Random(401))
    turn_pro(improved, rng=random.Random(401))

    for state in (base, improved):
        state.boxer.profile.age = 45
        state.career_months = 11
        state.boxer.aging_profile.peak_age = 28
        state.boxer.aging_profile.decline_onset_age = 30
        state.boxer.aging_profile.decline_severity = 1.0
        state.boxer.aging_profile.iq_growth_factor = 1.0
        stats = state.boxer.stats.to_dict()
        stats["speed"] = 84
        stats["stamina"] = 83
        stats["footwork"] = 82
        stats["chin"] = 81
        stats["power"] = 80
        state.boxer.stats = Stats.from_dict(stats)

    improved.pro_career.purse_balance = 30000.0
    purchase_staff_upgrade(improved, "sports_science")
    purchase_staff_upgrade(improved, "sports_science")
    purchase_staff_upgrade(improved, "sports_science")

    speed_before_base = base.boxer.stats.speed
    speed_before_improved = improved.boxer.stats.speed
    advance_month(base, months=1)
    advance_month(improved, months=1)

    base_drop = speed_before_base - base.boxer.stats.speed
    improved_drop = speed_before_improved - improved.boxer.stats.speed
    assert improved_drop < base_drop


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
    assert state.boxer.experience_points > 0
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
    assert status.min_age == 18
    assert status.min_fights == 10
    assert status.min_points == 100
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


def test_rankings_snapshot_uses_org_champion_at_number_one() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(111))
    division = state.boxer.division
    state.pro_career.rankings["WBC"] = 8
    state.pro_career.organization_champions["WBC"][division] = state.boxer.profile.name
    state.pro_career.organization_defenses["WBC"][division] = 2

    rows = rankings_snapshot(state, "WBC", top_n=5)
    player_row = next(row for row in rows if row.is_player)

    assert player_row.rank == 1
    assert state.pro_career.rankings["WBC"] == 1


def test_rankings_snapshot_demotes_stale_player_number_one_if_not_champion() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(112))
    division = state.boxer.division
    state.pro_career.rankings["WBC"] = 1
    state.pro_career.organization_champions["WBC"][division] = "External Champion"

    rows = rankings_snapshot(state, "WBC", top_n=5)
    top_row = rows[0]
    player_row = next(row for row in rows if row.is_player)

    assert top_row.name == "External Champion"
    assert player_row.rank == 2
    assert state.pro_career.rankings["WBC"] == 2


def test_pound_for_pound_snapshot_includes_player() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(5))
    state.pro_career.record = CareerRecord(wins=24, losses=1, draws=1, kos=13)
    for org_name in state.pro_career.rankings:
        state.pro_career.rankings[org_name] = 2

    rows = pound_for_pound_snapshot(state, top_n=20)
    player_rows = [row for row in rows if row.is_player]

    assert len(player_rows) == 1
    assert player_rows[0].rank <= 20
    assert player_rows[0].division == state.boxer.division


def test_change_division_vacates_lineal_and_seeds_rank() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(11))
    state.pro_career.record = CareerRecord(wins=19, losses=1, draws=0, kos=10)
    for org_name in state.pro_career.rankings:
        state.pro_career.rankings[org_name] = 3

    current_division = state.boxer.division
    state.pro_career.lineal_champions[current_division] = state.boxer.profile.name
    state.pro_career.lineal_defenses[current_division] = 2

    result = change_division(state, "super_welterweight", rng=random.Random(9))

    assert state.boxer.division == "super_welterweight"
    assert result["vacated_lineal"] == 1
    assert state.pro_career.lineal_champions[current_division] is None
    assert state.pro_career.division_changes == 1
    assert result["seed_rank"] is not None
    assert any(rank is not None for rank in state.pro_career.rankings.values())


def test_lineal_vacancy_allows_one_vs_three_fallback() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(13))
    focus_org = state.pro_career.organization_focus
    state.pro_career.rankings[focus_org] = 1
    state.pro_career.lineal_champions[state.boxer.division] = None

    opponent = Opponent(
        name="Vacancy Challenger",
        age=27,
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
        division=state.boxer.division,
        stats=state.boxer.stats,
        rating=89,
        record=CareerRecord(wins=20, losses=2, draws=1, kos=12),
        ranking_position=3,
        is_lineal_champion=False,
    )
    result = FightResult(
        winner=state.boxer.profile.name,
        method="UD",
        rounds_completed=10,
        scorecards=["97-93", "96-94", "98-92"],
        round_log=[],
    )
    purse = {
        "gross": 10000.0,
        "manager_cut": 1000.0,
        "trainer_cut": 1000.0,
        "camp_cost": 800.0,
        "commission_cut": 600.0,
        "sanction_fee": 300.0,
        "total_expenses": 3700.0,
        "net": 6300.0,
    }

    apply_pro_fight_result(state, opponent, result, purse)

    assert player_lineal_division(state) == state.boxer.division
    assert "Captured vacant lineal title" in state.history[-1].notes


def test_change_division_down_move_applies_major_penalties() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(21))

    fatigue_before = state.boxer.fatigue
    injury_before = state.boxer.injury_risk
    result = change_division(state, "super_lightweight", rng=random.Random(1))

    assert state.boxer.division == "super_lightweight"
    assert result["moving_down"] == 1
    assert int(result["injury_risk_gain"]) >= 14
    assert state.boxer.fatigue > fatigue_before
    assert state.boxer.injury_risk > injury_before


def test_pro_result_type_changes_post_fight_wear() -> None:
    purse = {
        "gross": 9000.0,
        "manager_cut": 900.0,
        "trainer_cut": 900.0,
        "camp_cost": 720.0,
        "commission_cut": 540.0,
        "sanction_fee": 0.0,
        "total_expenses": 3060.0,
        "net": 5940.0,
    }

    win_state = _build_pro_ready_state()
    loss_state = _build_pro_ready_state()
    turn_pro(win_state, rng=random.Random(55))
    turn_pro(loss_state, rng=random.Random(55))

    opponent = generate_pro_opponent(win_state, rng=random.Random(88))

    win_result = FightResult(
        winner=win_state.boxer.profile.name,
        method="UD",
        rounds_completed=10,
        scorecards=["97-93", "96-94", "98-92"],
        round_log=[],
    )
    loss_result = FightResult(
        winner=opponent.name,
        method="TKO",
        rounds_completed=3,
        scorecards=[],
        round_log=[],
    )

    apply_pro_fight_result(win_state, opponent, win_result, purse)
    apply_pro_fight_result(loss_state, opponent, loss_result, purse)

    assert loss_state.boxer.fatigue > win_state.boxer.fatigue
    assert loss_state.boxer.injury_risk > win_state.boxer.injury_risk


def test_offer_purse_returns_multi_body_sanctioning_metadata() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(303))
    state.pro_career.rankings["WBC"] = 8
    state.pro_career.rankings["IBF"] = 11
    opponent = generate_pro_opponent(state, rng=random.Random(404))

    purse = offer_purse(state, opponent, rng=random.Random(505))

    assert "sanctioning_bodies" in purse
    bodies = purse["sanctioning_bodies"]
    assert isinstance(bodies, list)
    assert state.pro_career.organization_focus in bodies


def test_pro_fight_updates_rankings_for_all_sanctioned_bodies() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(606))
    state.pro_career.rankings["WBC"] = 10
    state.pro_career.rankings["IBF"] = 12
    state.pro_career.rankings["WBA"] = 9

    opponent = Opponent(
        name="Dual Body Opponent",
        age=29,
        stance="southpaw",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
        division=state.boxer.division,
        stats=state.boxer.stats,
        rating=87,
        record=CareerRecord(wins=24, losses=3, draws=1, kos=14),
        ranking_position=9,
        organization_ranks={"WBC": 9, "IBF": 10, "WBA": 8},
    )
    result = FightResult(
        winner=state.boxer.profile.name,
        method="UD",
        rounds_completed=10,
        scorecards=["97-93", "96-94", "98-92"],
        round_log=[],
    )
    purse = {
        "gross": 12000.0,
        "manager_cut": 1200.0,
        "trainer_cut": 1200.0,
        "camp_cost": 960.0,
        "commission_cut": 720.0,
        "sanction_fee": 400.0,
        "total_expenses": 4480.0,
        "net": 7520.0,
        "sanctioning_bodies": ["WBC", "IBF"],
    }

    wbc_before = state.pro_career.rankings["WBC"]
    ibf_before = state.pro_career.rankings["IBF"]
    wba_before = state.pro_career.rankings["WBA"]
    apply_pro_fight_result(state, opponent, result, purse)

    assert state.pro_career.rankings["WBC"] < wbc_before
    assert state.pro_career.rankings["IBF"] < ibf_before
    assert state.pro_career.rankings["WBA"] == wba_before


def test_champion_draw_does_not_demote_rank() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(808))
    division = state.boxer.division
    org_name = "WBC"
    state.pro_career.organization_champions[org_name][division] = state.boxer.profile.name
    state.pro_career.rankings[org_name] = 1

    opponent = Opponent(
        name="Title Challenger",
        age=30,
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
        division=division,
        stats=state.boxer.stats,
        rating=88,
        record=CareerRecord(wins=21, losses=2, draws=1, kos=12),
        ranking_position=3,
        organization_ranks={org_name: 3},
    )
    result = FightResult(
        winner="Draw",
        method="MD",
        rounds_completed=10,
        scorecards=["95-95", "96-94", "94-96"],
        round_log=[],
    )
    purse = {
        "gross": 11000.0,
        "manager_cut": 1100.0,
        "trainer_cut": 1100.0,
        "camp_cost": 880.0,
        "commission_cut": 660.0,
        "sanction_fee": 330.0,
        "total_expenses": 4070.0,
        "net": 6930.0,
        "sanctioning_bodies": [org_name],
    }

    apply_pro_fight_result(state, opponent, result, purse)

    assert state.pro_career.rankings[org_name] == 1


def test_sanctioning_policy_can_exclude_focus_org(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(909))
    division = state.boxer.division
    focus_org = state.pro_career.organization_focus
    for org_name in state.pro_career.organization_champions:
        state.pro_career.organization_champions[org_name][division] = "Someone Else"

    opponent = Opponent(
        name="No Body Opponent",
        age=28,
        stance="southpaw",
        height_ft=5,
        height_in=9,
        weight_lbs=147,
        division=division,
        stats=state.boxer.stats,
        rating=82,
        record=CareerRecord(wins=18, losses=3, draws=0, kos=9),
        ranking_position=None,
        organization_ranks={},
    )

    monkeypatch.setattr(
        "boxing_game.modules.pro_career._sanctioning_policy",
        lambda: {
            "include_focus_org_always": False,
            "cross_body_top_window_prob": 0.0,
            "cross_body_elite_prob": 0.0,
            "cross_body_rank_gap_prob": 0.0,
            "cross_body_single_top10_prob": 0.0,
            "cross_body_rank_window": 20,
            "cross_body_elite_cutoff": 15,
            "cross_body_rank_gap_max": 8,
            "opponent_cross_rank_presence_prob": 0.0,
            "opponent_unranked_pool_rank_chance": 0.0,
            "opponent_cross_rank_jitter": 5,
            "tier_probability_multipliers": {"prospect": 1.0, "contender": 1.0, "ranked": 1.0},
        },
    )

    bodies = determine_sanctioning_bodies(state, opponent, rng=random.Random(910))

    assert bodies == []
    assert focus_org not in bodies


def test_history_entry_stores_structured_sanctioning_metadata() -> None:
    state = _build_pro_ready_state()
    turn_pro(state, rng=random.Random(990))
    opponent = Opponent(
        name="Metadata Opponent",
        age=27,
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=147,
        division=state.boxer.division,
        stats=state.boxer.stats,
        rating=86,
        record=CareerRecord(wins=20, losses=3, draws=1, kos=11),
        ranking_position=10,
        organization_ranks={"WBC": 10, "IBF": 11},
    )
    result = FightResult(
        winner=state.boxer.profile.name,
        method="UD",
        rounds_completed=10,
        scorecards=["97-93", "96-94", "98-92"],
        round_log=[],
    )
    purse = {
        "gross": 10000.0,
        "manager_cut": 1000.0,
        "trainer_cut": 1000.0,
        "camp_cost": 800.0,
        "commission_cut": 600.0,
        "sanction_fee": 300.0,
        "total_expenses": 3700.0,
        "net": 6300.0,
        "sanctioning_bodies": ["WBC", "IBF"],
    }

    apply_pro_fight_result(state, opponent, result, purse)
    entry = state.history[-1]

    assert entry.sanctioning_bodies == ["WBC", "IBF"]
    assert "WBC" in entry.ranking_updates


def test_sanctioning_tier_multiplier_increases_cross_body_frequency() -> None:
    prospect = _build_pro_ready_state()
    ranked = _build_pro_ready_state()
    turn_pro(prospect, rng=random.Random(707))
    turn_pro(ranked, rng=random.Random(707))

    for state in (prospect, ranked):
        state.pro_career.rankings["WBC"] = 8
        state.pro_career.rankings["WBA"] = 9
        state.pro_career.rankings["IBF"] = 7
        state.pro_career.rankings["WBO"] = 10

    ranked.pro_career.record = CareerRecord(wins=18, losses=2, draws=0, kos=9)

    prospect_counts: list[int] = []
    ranked_counts: list[int] = []
    for idx in range(40):
        opp_prospect = generate_pro_opponent(prospect, rng=random.Random(1000 + idx))
        purse_prospect = offer_purse(prospect, opp_prospect, rng=random.Random(2000 + idx))
        prospect_counts.append(len(purse_prospect["sanctioning_bodies"]))

        opp_ranked = generate_pro_opponent(ranked, rng=random.Random(3000 + idx))
        purse_ranked = offer_purse(ranked, opp_ranked, rng=random.Random(4000 + idx))
        ranked_counts.append(len(purse_ranked["sanctioning_bodies"]))

    prospect_avg = sum(prospect_counts) / len(prospect_counts)
    ranked_avg = sum(ranked_counts) / len(ranked_counts)
    assert ranked_avg > prospect_avg
