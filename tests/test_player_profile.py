import pytest

from boxing_game.constants import STARTING_AGE
from boxing_game.modules.player_profile import create_boxer


def test_create_boxer_uses_height_weight_for_stats_and_division() -> None:
    boxer = create_boxer(
        name="Test Boxer",
        stance="orthodox",
        height_ft=5,
        height_in=11,
        weight_lbs=147,
    )

    assert boxer.profile.age == STARTING_AGE
    assert boxer.division == "welterweight"
    assert boxer.stats.reach_control >= 55


def test_create_boxer_requires_non_empty_name() -> None:
    with pytest.raises(ValueError, match="Name is required"):
        create_boxer(
            name="   ",
            stance="orthodox",
            height_ft=5,
            height_in=11,
            weight_lbs=147,
        )
