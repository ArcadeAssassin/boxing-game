from __future__ import annotations

from boxing_game.models import Stats
from boxing_game.modules.weight_class_engine import WeightClass
from boxing_game.rules_registry import load_rule_set


def _clamp(value: float, lower: int, upper: int) -> int:
    return max(lower, min(upper, int(round(value))))


def build_stats(
    *,
    height_inches: int,
    weight_lbs: int,
    weight_class: WeightClass,
) -> Stats:
    rules = load_rule_set("attribute_model")
    base = rules["base_stats"]
    min_stat = int(rules["stat_limits"]["min"])
    max_stat = int(rules["stat_limits"]["max"])

    frame_delta = height_inches - weight_class.avg_height_in
    class_span = max(1, weight_class.max_lbs - weight_class.min_lbs)
    weight_position = (weight_lbs - weight_class.min_lbs) / class_span
    heaviness = (weight_position - 0.5) * 2.0

    values: dict[str, int] = {}
    for stat_name, base_value in base.items():
        height_coeff = float(rules["height_coefficients"].get(stat_name, 0.0))
        weight_coeff = float(rules["weight_coefficients"].get(stat_name, 0.0))
        adjusted = base_value + (frame_delta * height_coeff) + (heaviness * weight_coeff)
        values[stat_name] = _clamp(adjusted, min_stat, max_stat)

    return Stats(
        power=values["power"],
        speed=values["speed"],
        chin=values["chin"],
        stamina=values["stamina"],
        defense=values["defense"],
        ring_iq=values["ring_iq"],
        footwork=values["footwork"],
        reach_control=values["reach_control"],
        inside_fighting=values["inside_fighting"],
    )


def training_gain(stats: Stats, focus: str) -> Stats:
    fields = stats.to_dict()
    if focus not in fields:
        raise ValueError(f"Unknown focus area: {focus}")

    rules = load_rule_set("attribute_model")
    max_stat = int(rules["stat_limits"]["max"])

    fields[focus] = min(max_stat, fields[focus] + 2)

    if focus in ("power", "chin"):
        fields["speed"] = max(20, fields["speed"] - 1)
    if focus in ("speed", "footwork"):
        fields["power"] = max(20, fields["power"] - 1)

    return Stats.from_dict(fields)
