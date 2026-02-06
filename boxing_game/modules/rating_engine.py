from __future__ import annotations

from boxing_game.models import Boxer, Stats
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


def boxer_overall_rating(boxer: Boxer, *, stage: str) -> int:
    model_key = "pro" if stage == "pro" else "amateur"
    base = _weighted_rating(boxer.stats, model_key)
    fatigue_penalty = int(round(boxer.fatigue * 0.5))
    return max(20, base - fatigue_penalty)
