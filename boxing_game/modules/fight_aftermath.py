from __future__ import annotations

from dataclasses import dataclass

from boxing_game.models import FightResult
from boxing_game.rules_registry import load_rule_set


@dataclass(frozen=True)
class PostFightImpact:
    fatigue_gain: int
    injury_risk_gain: int


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _outcome_key(boxer_name: str, result: FightResult) -> str:
    if result.winner == boxer_name:
        return "win"
    if result.winner == "Draw":
        return "draw"
    return "loss"


def _multiplier(
    config: dict,
    *,
    section: str,
    outcome_key: str,
    stat_key: str,
) -> float:
    section_payload = config.get(section, {})
    if not isinstance(section_payload, dict):
        return 1.0

    outcome_payload = section_payload.get(outcome_key, {})
    if not isinstance(outcome_payload, dict):
        return 1.0

    try:
        return float(outcome_payload.get(stat_key, 1.0))
    except (TypeError, ValueError):
        return 1.0


def _rounds_factor(
    *,
    rounds_completed: int,
    rounds_scheduled: int,
    rounds_weight: float,
) -> float:
    completion_ratio = _clamp_float(
        float(max(0, rounds_completed)) / float(max(1, rounds_scheduled)),
        0.0,
        1.0,
    )
    weight = _clamp_float(rounds_weight, 0.0, 1.0)
    return (1.0 - weight) + (completion_ratio * weight)


def _rounded_gain(value: float, *, base_gain: int) -> int:
    if base_gain <= 0:
        return 0
    return max(1, int(round(value)))


def calculate_post_fight_impact(
    *,
    stage: str,
    boxer_name: str,
    result: FightResult,
    rounds_scheduled: int,
) -> PostFightImpact:
    if rounds_scheduled < 1:
        raise ValueError("rounds_scheduled must be >= 1.")

    fight_models = load_rule_set("fight_model")
    if stage not in fight_models:
        raise ValueError(f"Unknown fight stage: {stage}")

    stage_cfg = fight_models[stage]
    impact_cfg = stage_cfg.get("post_fight_effects", {})
    if not isinstance(impact_cfg, dict):
        impact_cfg = {}

    default_fatigue = 3 if stage == "amateur" else 4
    default_injury = 4 if stage == "amateur" else 5
    base_fatigue = max(0, int(impact_cfg.get("base_fatigue_gain", default_fatigue)))
    base_injury = max(0, int(impact_cfg.get("base_injury_risk_gain", default_injury)))

    outcome = _outcome_key(boxer_name, result)
    rounds_factor = _rounds_factor(
        rounds_completed=result.rounds_completed,
        rounds_scheduled=rounds_scheduled,
        rounds_weight=float(impact_cfg.get("rounds_completed_weight", 0.35)),
    )

    fatigue = float(base_fatigue)
    fatigue *= _multiplier(
        impact_cfg,
        section="outcome_multipliers",
        outcome_key=outcome,
        stat_key="fatigue",
    )
    fatigue *= rounds_factor

    injury = float(base_injury)
    injury *= _multiplier(
        impact_cfg,
        section="outcome_multipliers",
        outcome_key=outcome,
        stat_key="injury",
    )
    injury *= rounds_factor

    if result.method in {"KO", "TKO"}:
        fatigue *= _multiplier(
            impact_cfg,
            section="stoppage_multipliers",
            outcome_key=outcome,
            stat_key="fatigue",
        )
        injury *= _multiplier(
            impact_cfg,
            section="stoppage_multipliers",
            outcome_key=outcome,
            stat_key="injury",
        )

    return PostFightImpact(
        fatigue_gain=_rounded_gain(fatigue, base_gain=base_fatigue),
        injury_risk_gain=_rounded_gain(injury, base_gain=base_injury),
    )
