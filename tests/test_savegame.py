import json
from pathlib import Path

import pytest

from boxing_game.constants import STARTING_AGE
from boxing_game.models import CareerState
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.savegame import SavegameError, list_saves, load_state, save_state


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    boxer = create_boxer(
        name="Saver",
        stance="southpaw",
        height_ft=5,
        height_in=8,
        weight_lbs=135,
    )
    state = CareerState(boxer=boxer)
    state.boxer.amateur_points = 17

    save_state(state, "slot_one", save_dir=tmp_path)
    loaded = load_state("slot_one", save_dir=tmp_path)

    assert loaded.boxer.profile.name == "Saver"
    assert loaded.boxer.amateur_points == 17
    assert list_saves(save_dir=tmp_path) == ["slot_one"]


def test_load_rejects_newer_save_version(tmp_path: Path) -> None:
    path = tmp_path / "future_slot.json"
    path.write_text(
        json.dumps({"version": 999, "career": {}}),
        encoding="utf-8",
    )

    with pytest.raises(SavegameError, match="newer than supported"):
        load_state("future_slot", save_dir=tmp_path)


def test_load_legacy_save_backfills_age_from_calendar(tmp_path: Path) -> None:
    boxer = create_boxer(
        name="Legacy",
        stance="orthodox",
        height_ft=5,
        height_in=9,
        weight_lbs=140,
    )
    boxer.profile.age = STARTING_AGE
    state = CareerState(boxer=boxer, month=1, year=4)
    payload = {"version": 1, "career": state.to_dict()}
    payload["career"].pop("career_months", None)

    path = tmp_path / "legacy_slot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_state("legacy_slot", save_dir=tmp_path)

    assert loaded.career_months == 36
    assert loaded.boxer.profile.age == STARTING_AGE + 3
