"""Weight-class assignment engine.

Reads the weight-class table from ``rules/weight_classes.json`` and
provides lookup/classification functions.
"""

from __future__ import annotations

from dataclasses import dataclass

from boxing_game.rules_registry import load_rule_set


@dataclass(frozen=True)
class WeightClass:
    """A single weight division with its limits and average height."""

    name: str
    min_lbs: int
    max_lbs: int
    avg_height_in: int


def list_weight_classes() -> list[WeightClass]:
    """Return every configured weight class ordered from lightest to heaviest."""
    payload = load_rule_set("weight_classes")
    return [
        WeightClass(
            name=raw["name"],
            min_lbs=int(raw["min_lbs"]),
            max_lbs=int(raw["max_lbs"]),
            avg_height_in=int(raw["avg_height_in"]),
        )
        for raw in payload["classes"]
    ]


def classify_weight(weight_lbs: int) -> WeightClass:
    """Return the weight class that contains *weight_lbs*.

    If the weight falls below the lightest class or above the heaviest,
    the nearest boundary class is returned.
    """
    classes = list_weight_classes()
    for weight_class in classes:
        if weight_class.min_lbs <= weight_lbs <= weight_class.max_lbs:
            return weight_class
    if weight_lbs < classes[0].min_lbs:
        return classes[0]
    return classes[-1]
