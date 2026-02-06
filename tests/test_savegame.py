import json
from pathlib import Path

import pytest

from boxing_game.constants import STARTING_AGE
from boxing_game.models import CareerRecord, CareerState
from boxing_game.modules.experience_engine import infer_points_from_total_fights
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.savegame import (
    SavegameError,
    duplicate_state,
    delete_state,
    list_saves,
    list_save_metadata,
    load_state,
    rename_state,
    save_state,
)


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
    state.boxer.experience_points = 55

    save_state(state, "slot_one", save_dir=tmp_path)
    loaded = load_state("slot_one", save_dir=tmp_path)

    assert loaded.boxer.profile.name == "Saver"
    assert loaded.boxer.amateur_points == 17
    assert loaded.boxer.experience_points == 55
    assert list_saves(save_dir=tmp_path) == ["slot_one"]


def test_load_rejects_newer_save_version(tmp_path: Path) -> None:
    path = tmp_path / "future_slot.json"
    path.write_text(
        json.dumps({"version": 999, "career": {}}),
        encoding="utf-8",
    )

    with pytest.raises(SavegameError, match="newer than supported"):
        load_state("future_slot", save_dir=tmp_path)


def test_delete_state_removes_slot(tmp_path: Path) -> None:
    boxer = create_boxer(
        name="Delete Me",
        stance="southpaw",
        height_ft=5,
        height_in=9,
        weight_lbs=135,
    )
    state = CareerState(boxer=boxer)
    save_state(state, "trash_slot", save_dir=tmp_path)

    deleted_path = delete_state("trash_slot", save_dir=tmp_path)

    assert deleted_path.name == "trash_slot.json"
    assert list_saves(save_dir=tmp_path) == []


def test_delete_state_rejects_missing_slot(tmp_path: Path) -> None:
    with pytest.raises(SavegameError, match="Save slot not found"):
        delete_state("missing_slot", save_dir=tmp_path)


def test_rename_state_moves_slot(tmp_path: Path) -> None:
    boxer = create_boxer(
        name="Rename Me",
        stance="southpaw",
        height_ft=5,
        height_in=8,
        weight_lbs=130,
    )
    state = CareerState(boxer=boxer)
    save_state(state, "old_slot", save_dir=tmp_path)

    renamed_path = rename_state("old_slot", "new_slot", save_dir=tmp_path)

    assert renamed_path.name == "new_slot.json"
    assert list_saves(save_dir=tmp_path) == ["new_slot"]


def test_duplicate_state_creates_second_slot(tmp_path: Path) -> None:
    boxer = create_boxer(
        name="Copy Me",
        stance="orthodox",
        height_ft=5,
        height_in=10,
        weight_lbs=140,
    )
    state = CareerState(boxer=boxer)
    save_state(state, "source_slot", save_dir=tmp_path)

    duplicate_path = duplicate_state("source_slot", "target_slot", save_dir=tmp_path)

    assert duplicate_path.name == "target_slot.json"
    assert list_saves(save_dir=tmp_path) == ["source_slot", "target_slot"]
    loaded = load_state("target_slot", save_dir=tmp_path)
    assert loaded.boxer.profile.name == "Copy Me"


def test_list_save_metadata_reads_saved_fields(tmp_path: Path) -> None:
    boxer = create_boxer(
        name="Meta Boxer",
        stance="orthodox",
        height_ft=6,
        height_in=0,
        weight_lbs=160,
    )
    state = CareerState(boxer=boxer, month=3, year=2)
    save_state(state, "meta_slot", save_dir=tmp_path)

    metadata = list_save_metadata(save_dir=tmp_path)

    assert len(metadata) == 1
    info = metadata[0]
    assert info.slot == "meta_slot"
    assert info.is_valid is True
    assert info.boxer_name == "Meta Boxer"
    assert info.month == 3
    assert info.year == 2
    assert info.saved_at


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


def test_load_legacy_save_backfills_experience_from_total_fights(tmp_path: Path) -> None:
    boxer = create_boxer(
        name="Legacy XP",
        stance="orthodox",
        height_ft=5,
        height_in=9,
        weight_lbs=140,
    )
    state = CareerState(boxer=boxer)
    state.boxer.record = CareerRecord(wins=5, losses=2, draws=1, kos=2)
    state.pro_career.record = CareerRecord(wins=4, losses=1, draws=0, kos=2)

    payload = {"version": 2, "career": state.to_dict()}
    payload["career"]["boxer"].pop("experience_points", None)

    path = tmp_path / "legacy_xp_slot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_state("legacy_xp_slot", save_dir=tmp_path)

    total_fights = 5 + 2 + 1 + 4 + 1 + 0
    assert loaded.boxer.experience_points == infer_points_from_total_fights(total_fights)


def test_load_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "broken_slot.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(SavegameError, match="not valid JSON"):
        load_state("broken_slot", save_dir=tmp_path)


def test_load_rejects_invalid_career_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad_career_slot.json"
    path.write_text(
        json.dumps({"version": 2, "career": {"month": 1}}),
        encoding="utf-8",
    )

    with pytest.raises(SavegameError, match="career payload is invalid"):
        load_state("bad_career_slot", save_dir=tmp_path)
