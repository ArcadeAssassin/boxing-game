"""Save/load/delete career state as JSON.

Supports atomic writes, slot management (rename/duplicate/delete),
and metadata listing for the GUI save-management page.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from boxing_game.constants import CURRENT_SAVE_VERSION
from boxing_game.models import CareerState
from boxing_game.utils import coerce_int

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAVE_DIR = PROJECT_ROOT / "saves"

_SLOT_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")


class SavegameError(ValueError):
    """Raised when save files are invalid or missing."""


@dataclass(frozen=True)
class SaveMetadata:
    """Lightweight metadata extracted from a save file without full load."""

    slot: str
    path: Path
    saved_at: str
    version: int | None
    boxer_name: str
    age: int | None
    division: str
    month: int | None
    year: int | None
    is_pro: bool | None
    is_valid: bool
    error: str = ""


# ---------------------------------------------------------------------------
# Slot validation
# ---------------------------------------------------------------------------

def _validate_slot(slot: str) -> str:
    candidate = slot.strip()
    if not _SLOT_PATTERN.match(candidate):
        raise SavegameError(
            "Save slot must be 1-40 chars and contain only letters, numbers, - or _."
        )
    return candidate


def _save_path(slot: str, save_dir: Path | None = None) -> Path:
    base = save_dir or DEFAULT_SAVE_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{slot}.json"


# ---------------------------------------------------------------------------
# Core I/O
# ---------------------------------------------------------------------------

def save_state(state: CareerState, slot: str, save_dir: Path | None = None) -> Path:
    """Persist *state* to the given save slot atomically."""
    normalized_slot = _validate_slot(slot)
    target_path = _save_path(normalized_slot, save_dir=save_dir)

    payload = {
        "version": CURRENT_SAVE_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "career": state.to_dict(),
    }
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8",
            dir=target_path.parent, prefix=f"{normalized_slot}.", suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(target_path)
    except OSError as exc:
        raise SavegameError(f"Failed to write save file: {exc}") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return target_path


def load_state(slot: str, save_dir: Path | None = None) -> CareerState:
    """Load and validate a career state from the given save slot."""
    normalized_slot = _validate_slot(slot)
    source_path = _save_path(normalized_slot, save_dir=save_dir)
    if not source_path.exists():
        raise SavegameError(f"Save slot not found: {normalized_slot}")

    try:
        with source_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise SavegameError("Save file is not valid JSON.") from exc
    except OSError as exc:
        raise SavegameError(f"Failed to read save file: {exc}") from exc

    if not isinstance(payload, dict):
        raise SavegameError("Save file is invalid.")

    try:
        version = int(payload.get("version", 1))
    except (TypeError, ValueError) as exc:
        raise SavegameError("Save file version is invalid.") from exc
    if version > CURRENT_SAVE_VERSION:
        raise SavegameError(
            f"Save version {version} is newer than supported version {CURRENT_SAVE_VERSION}."
        )

    if "career" not in payload:
        raise SavegameError("Save file missing career payload.")
    if not isinstance(payload["career"], dict):
        raise SavegameError("Save file career payload is invalid.")

    try:
        return CareerState.from_dict(payload["career"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SavegameError("Save file career payload is invalid.") from exc


# ---------------------------------------------------------------------------
# Slot management
# ---------------------------------------------------------------------------

def rename_state(slot: str, new_slot: str, save_dir: Path | None = None) -> Path:
    """Rename an existing save slot, returning the new path."""
    source_slot = _validate_slot(slot)
    target_slot = _validate_slot(new_slot)
    if source_slot == target_slot:
        raise SavegameError("Source and destination save slots must be different.")

    source_path = _save_path(source_slot, save_dir=save_dir)
    target_path = _save_path(target_slot, save_dir=save_dir)
    if not source_path.exists():
        raise SavegameError(f"Save slot not found: {source_slot}")
    if target_path.exists():
        raise SavegameError(f"Save slot already exists: {target_slot}")

    try:
        source_path.replace(target_path)
    except OSError as exc:
        raise SavegameError(f"Failed to rename save file: {exc}") from exc
    return target_path


def duplicate_state(slot: str, new_slot: str, save_dir: Path | None = None) -> Path:
    """Duplicate a save slot under a new name."""
    source_slot = _validate_slot(slot)
    target_slot = _validate_slot(new_slot)
    if source_slot == target_slot:
        raise SavegameError("Source and destination save slots must be different.")

    source_path = _save_path(source_slot, save_dir=save_dir)
    target_path = _save_path(target_slot, save_dir=save_dir)
    if not source_path.exists():
        raise SavegameError(f"Save slot not found: {source_slot}")
    if target_path.exists():
        raise SavegameError(f"Save slot already exists: {target_slot}")

    try:
        shutil.copy2(source_path, target_path)
    except OSError as exc:
        raise SavegameError(f"Failed to duplicate save file: {exc}") from exc
    return target_path


def delete_state(slot: str, save_dir: Path | None = None) -> Path:
    """Delete a save slot file."""
    normalized_slot = _validate_slot(slot)
    target_path = _save_path(normalized_slot, save_dir=save_dir)
    if not target_path.exists():
        raise SavegameError(f"Save slot not found: {normalized_slot}")

    try:
        target_path.unlink()
    except OSError as exc:
        raise SavegameError(f"Failed to delete save file: {exc}") from exc
    return target_path


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def _read_save_metadata(slot: str, path: Path) -> SaveMetadata:
    """Read lightweight metadata from a save file without full state load."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return _invalid_metadata(slot, path, "Invalid JSON")
    except OSError as exc:
        return _invalid_metadata(slot, path, f"Unreadable: {exc}")

    if not isinstance(payload, dict):
        return _invalid_metadata(slot, path, "Invalid payload")

    saved_at = str(payload.get("saved_at", ""))
    version = coerce_int(payload.get("version"))
    career = payload.get("career")
    if not isinstance(career, dict):
        return _invalid_metadata(slot, path, "Missing career payload", saved_at=saved_at, version=version)

    boxer = career.get("boxer")
    boxer_payload = boxer if isinstance(boxer, dict) else {}
    profile = boxer_payload.get("profile")
    profile_payload = profile if isinstance(profile, dict) else {}
    pro_career = career.get("pro_career")
    pro_payload = pro_career if isinstance(pro_career, dict) else {}

    boxer_name = str(profile_payload.get("name", "")).strip()
    division = str(boxer_payload.get("division", "")).strip()
    age = coerce_int(profile_payload.get("age"))
    month = coerce_int(career.get("month"))
    year = coerce_int(career.get("year"))
    is_pro_raw = pro_payload.get("is_active")
    is_pro = bool(is_pro_raw) if is_pro_raw is not None else None

    return SaveMetadata(
        slot=slot, path=path, saved_at=saved_at, version=version,
        boxer_name=boxer_name, age=age, division=division,
        month=month, year=year, is_pro=is_pro, is_valid=True,
    )


def _invalid_metadata(
    slot: str,
    path: Path,
    error: str,
    *,
    saved_at: str = "",
    version: int | None = None,
) -> SaveMetadata:
    """Construct a ``SaveMetadata`` for an unreadable/invalid save file."""
    return SaveMetadata(
        slot=slot, path=path, saved_at=saved_at, version=version,
        boxer_name="", age=None, division="", month=None, year=None,
        is_pro=None, is_valid=False, error=error,
    )


def _saved_at_sort_value(saved_at: str) -> datetime:
    if not saved_at:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(saved_at)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def list_save_metadata(save_dir: Path | None = None) -> list[SaveMetadata]:
    """Return metadata for all save slots, newest first."""
    base = save_dir or DEFAULT_SAVE_DIR
    if not base.exists():
        return []

    items: list[SaveMetadata] = []
    for path in base.glob("*.json"):
        if not path.is_file() or not _SLOT_PATTERN.match(path.stem):
            continue
        items.append(_read_save_metadata(path.stem, path))

    items.sort(
        key=lambda item: (_saved_at_sort_value(item.saved_at), item.slot),
        reverse=True,
    )
    return items


def list_saves(save_dir: Path | None = None) -> list[str]:
    """Return a sorted list of save slot names."""
    base = save_dir or DEFAULT_SAVE_DIR
    if not base.exists():
        return []

    slots: list[str] = []
    for path in base.glob("*.json"):
        if path.is_file() and _SLOT_PATTERN.match(path.stem):
            slots.append(path.stem)
    return sorted(slots)
