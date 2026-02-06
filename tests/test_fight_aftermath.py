from boxing_game.models import FightResult
from boxing_game.modules.fight_aftermath import calculate_post_fight_impact


def test_pro_stoppage_loss_has_more_wear_than_decision_win() -> None:
    boxer_name = "Result Fighter"
    decision_win = FightResult(
        winner=boxer_name,
        method="UD",
        rounds_completed=10,
        scorecards=[],
        round_log=[],
    )
    stoppage_loss = FightResult(
        winner="Danger Opponent",
        method="TKO",
        rounds_completed=3,
        scorecards=[],
        round_log=[],
    )

    win_impact = calculate_post_fight_impact(
        stage="pro",
        boxer_name=boxer_name,
        result=decision_win,
        rounds_scheduled=10,
    )
    loss_impact = calculate_post_fight_impact(
        stage="pro",
        boxer_name=boxer_name,
        result=stoppage_loss,
        rounds_scheduled=10,
    )

    assert loss_impact.fatigue_gain > win_impact.fatigue_gain
    assert loss_impact.injury_risk_gain > win_impact.injury_risk_gain


def test_amateur_short_stoppage_win_has_less_wear_than_full_decision() -> None:
    boxer_name = "Fast Finisher"
    full_decision = FightResult(
        winner=boxer_name,
        method="UD",
        rounds_completed=3,
        scorecards=[],
        round_log=[],
    )
    short_stoppage = FightResult(
        winner=boxer_name,
        method="TKO",
        rounds_completed=1,
        scorecards=[],
        round_log=[],
    )

    decision_impact = calculate_post_fight_impact(
        stage="amateur",
        boxer_name=boxer_name,
        result=full_decision,
        rounds_scheduled=3,
    )
    stoppage_impact = calculate_post_fight_impact(
        stage="amateur",
        boxer_name=boxer_name,
        result=short_stoppage,
        rounds_scheduled=3,
    )

    assert stoppage_impact.fatigue_gain < decision_impact.fatigue_gain
    assert stoppage_impact.injury_risk_gain < decision_impact.injury_risk_gain
