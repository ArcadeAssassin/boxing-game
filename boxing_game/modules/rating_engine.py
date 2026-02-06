from __future__ import annotations

from boxing_game.models import Boxer, CareerRecord, Stats
from boxing_game.modules.experience_engine import boxer_experience_profile
from boxing_game.rules_registry import load_rule_set


def _weighted_rating(stats: Stats, model_key: str) -> int:
    models = load_rule_set("fight_model")
    if model_key not in models:
        raise ValueError(f"Unknown rating model: {model_key}")
    weights = {str(k): float(v) for k, v in models[model_key]["style_weights"].items()}

    values = stats.to_dict()
    weighted_total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        if key not in values:
            continue
        weighted_total += values[key] * weight
        weight_sum += weight

    if weight_sum <= 0:
        return 20
    return max(20, min(99, int(round(weighted_total / weight_sum))))


def boxer_overall_rating(
    boxer: Boxer,
    *,
    stage: str,
    pro_record: CareerRecord | None = None,
) -> int:
    model_key = "pro" if stage == "pro" else "amateur"
    base = _weighted_rating(boxer.stats, model_key)
    experience_bonus = boxer_experience_profile(
        boxer,
        pro_record=pro_record,
    ).fight_bonus
    fatigue_penalty = int(round(boxer.fatigue * 0.5))
    adjusted = int(round(base + experience_bonus)) - fatigue_penalty
    return max(20, min(99, adjusted))
