from boxing_game.models import Boxer
from boxing_game.modules.aging_engine import generate_aging_profile
from boxing_game.modules.player_profile import create_boxer


def test_generate_aging_profile_is_deterministic() -> None:
    first = generate_aging_profile(
        name="Stable Prospect",
        stance="orthodox",
        height_inches=70,
        weight_lbs=147,
    )
    second = generate_aging_profile(
        name="Stable Prospect",
        stance="orthodox",
        height_inches=70,
        weight_lbs=147,
    )

    assert first == second


def test_generate_aging_profile_bounds() -> None:
    profile = generate_aging_profile(
        name="Bounds Check",
        stance="southpaw",
        height_inches=77,
        weight_lbs=265,
    )

    assert 24 <= profile.peak_age <= 34
    assert profile.peak_age <= profile.decline_onset_age <= 40
    assert 0.7 <= profile.decline_severity <= 1.4
    assert 0.75 <= profile.iq_growth_factor <= 1.35


def test_boxer_from_dict_backfills_missing_aging_profile() -> None:
    boxer = create_boxer(
        name="Legacy Save Boxer",
        stance="orthodox",
        height_ft=6,
        height_in=1,
        weight_lbs=175,
    )
    payload = boxer.to_dict()
    payload.pop("aging_profile", None)

    restored = Boxer.from_dict(payload)
    expected = generate_aging_profile(
        name=boxer.profile.name,
        stance=boxer.profile.stance,
        height_inches=boxer.profile.height_inches,
        weight_lbs=boxer.profile.weight_lbs,
    )

    assert restored.aging_profile == expected
