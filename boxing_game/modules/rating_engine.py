"""Weighted overall boxer rating.

Computes a single ``int`` rating (20-99) for a boxer by combining
weighted fight-model stats, experience bonus, and fatigue penalty.
"""

from __future__ import annotations

from boxing_game.models import Boxer, CareerRecord, Stats
from boxing_game.modules.experience_engine import boxer_experience_profile
from boxing_game.rules_registry import load_rule_set
from boxing_game.utils import clamp_int


def _weighted_rating(stats: Stats, model_key: str) -> int:
    """Compute the weighted rating for *stats* using the given fight model."""
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
    return clamp_int(int(round(weighted_total / weight_sum)), 20, 99)


def boxer_overall_rating(
    boxer: Boxer,
    *,
    stage: str,
    pro_record: CareerRecord | None = None,
) -> int:
    """Return a composite overall rating for *boxer* (20-99).

    Combines the weighted stat rating with an experience bonus and
    subtracts a fatigue penalty.
    """
    model_key = "pro" if stage == "pro" else "amateur"
    base = _weighted_rating(boxer.stats, model_key)
    experience_bonus = boxer_experience_profile(
        boxer,
        pro_record=pro_record,
    ).fight_bonus
    fatigue_penalty = int(round(boxer.fatigue * 0.5))
    adjusted = int(round(base + experience_bonus)) - fatigue_penalty
    return clamp_int(adjusted, 20, 99)
