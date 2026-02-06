from boxing_game.models import CareerRecord, FightResult, Opponent, Stats
from boxing_game.modules.experience_engine import (
    boxer_experience_profile,
    fight_experience_gain,
    infer_points_from_total_fights,
    opponent_experience_profile,
    profile_from_points,
    total_career_fights,
)
from boxing_game.modules.player_profile import create_boxer


def _sample_result(*, winner: str, method: str = "UD") -> FightResult:
    return FightResult(
        winner=winner,
        method=method,
        rounds_completed=3,
        scorecards=["29-28", "29-28", "28-29"],
        round_log=["R1: test"],
    )


def test_profile_from_points_advances_levels() -> None:
    rookie = profile_from_points(0)
    veteran = profile_from_points(200)

    assert rookie.level == 1
    assert rookie.title == "newcomer"
    assert rookie.fight_bonus == 0.0
    assert veteran.level > rookie.level
    assert veteran.fight_bonus > rookie.fight_bonus


def test_fight_experience_gain_varies_by_stage_and_result() -> None:
    boxer_name = "XP Boxer"
    pro_win = fight_experience_gain(
        stage="pro",
        boxer_name=boxer_name,
        opponent_rating=82,
        result=_sample_result(winner=boxer_name, method="TKO"),
    )
    amateur_loss = fight_experience_gain(
        stage="amateur",
        boxer_name=boxer_name,
        opponent_rating=55,
        result=_sample_result(winner="Other Boxer"),
    )

    assert pro_win > amateur_loss
    assert pro_win >= 1


def test_boxer_and_opponent_experience_profiles_use_fights() -> None:
    boxer = create_boxer(
        name="Fallback XP",
        stance="orthodox",
        height_ft=5,
        height_in=11,
        weight_lbs=154,
    )
    boxer.record = CareerRecord(wins=4, losses=1, draws=1, kos=2)
    pro_record = CareerRecord(wins=3, losses=0, draws=0, kos=1)

    profile = boxer_experience_profile(boxer, pro_record=pro_record)
    expected_total_fights = total_career_fights(boxer, pro_record=pro_record)
    assert profile.points == infer_points_from_total_fights(expected_total_fights)

    opponent = Opponent(
        name="CPU",
        age=26,
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=154,
        division="welterweight",
        stats=Stats(
            power=62,
            speed=60,
            chin=59,
            stamina=61,
            defense=57,
            ring_iq=60,
            footwork=58,
            reach_control=57,
            inside_fighting=56,
        ),
        rating=72,
        record=CareerRecord(wins=10, losses=2, draws=1, kos=5),
    )
    opponent_profile = opponent_experience_profile(opponent)
    assert opponent_profile.points == infer_points_from_total_fights(13)
