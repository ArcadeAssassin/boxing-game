"""Boxer creation and input validation.

Handles validated boxer creation with height/weight sanity checks and
automatic stat/aging-profile generation.
"""

from __future__ import annotations

from boxing_game.constants import STARTING_AGE
from boxing_game.models import Boxer, BoxerProfile, CareerRecord
from boxing_game.modules.aging_engine import generate_aging_profile
from boxing_game.modules.attribute_engine import build_stats
from boxing_game.modules.weight_class_engine import classify_weight

VALID_STANCES: set[str] = {"orthodox", "southpaw"}


def validate_body_metrics(height_ft: int, height_in: int, weight_lbs: int) -> None:
    """Raise ``ValueError`` if any body metric is out of its valid range."""
    if not 4 <= height_ft <= 7:
        raise ValueError("Height feet must be between 4 and 7.")
    if not 0 <= height_in <= 11:
        raise ValueError("Height inches must be between 0 and 11.")
    if not 90 <= weight_lbs <= 300:
        raise ValueError("Weight must be between 90 and 300 lbs.")


def create_boxer(
    *,
    name: str,
    stance: str,
    height_ft: int,
    height_in: int,
    weight_lbs: int,
    nationality: str = "USA",
) -> Boxer:
    """Create a new boxer with auto-generated stats and aging profile.

    Validates all inputs, classifies the weight division, and generates
    a deterministic aging profile from the boxer's identity.
    """
    validate_body_metrics(height_ft, height_in, weight_lbs)

    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Name is required.")

    normalized_nationality = nationality.strip() or "USA"

    normalized_stance = stance.strip().lower()
    if normalized_stance not in VALID_STANCES:
        raise ValueError("Stance must be orthodox or southpaw.")

    weight_class = classify_weight(weight_lbs)
    height_inches = height_ft * 12 + height_in

    profile = BoxerProfile(
        name=normalized_name,
        age=STARTING_AGE,
        stance=normalized_stance,
        height_ft=height_ft,
        height_in=height_in,
        weight_lbs=weight_lbs,
        reach_in=height_inches + 1,
        nationality=normalized_nationality,
    )
    stats = build_stats(
        height_inches=height_inches,
        weight_lbs=weight_lbs,
        weight_class=weight_class,
    )
    aging_profile = generate_aging_profile(
        name=normalized_name,
        stance=normalized_stance,
        height_inches=height_inches,
        weight_lbs=weight_lbs,
    )

    return Boxer(
        profile=profile,
        stats=stats,
        division=weight_class.name,
        record=CareerRecord(),
        aging_profile=aging_profile,
    )
