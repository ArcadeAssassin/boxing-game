from __future__ import annotations

from dataclasses import dataclass

from boxing_game.rules_registry import load_rule_set


@dataclass(frozen=True)
class WeightClass:
    name: str
    min_lbs: int
    max_lbs: int
    avg_height_in: int


def list_weight_classes() -> list[WeightClass]:
    payload = load_rule_set("weight_classes")
    classes = []
    for raw in payload["classes"]:
        classes.append(
            WeightClass(
                name=raw["name"],
                min_lbs=int(raw["min_lbs"]),
                max_lbs=int(raw["max_lbs"]),
                avg_height_in=int(raw["avg_height_in"]),
            )
        )
    return classes


def classify_weight(weight_lbs: int) -> WeightClass:
    classes = list_weight_classes()
    for weight_class in classes:
        if weight_class.min_lbs <= weight_lbs <= weight_class.max_lbs:
            return weight_class
    if weight_lbs < classes[0].min_lbs:
        return classes[0]
    return classes[-1]
