from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from boxing_game.models import CareerState

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAVE_DIR = PROJECT_ROOT / "saves"
CURRENT_SAVE_VERSION = 2

_SLOT_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")


class SavegameError(ValueError):
    """Raised when save files are invalid or missing."""


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


def save_state(state: CareerState, slot: str, save_dir: Path | None = None) -> Path:
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
            "w",
            encoding="utf-8",
            dir=target_path.parent,
            prefix=f"{normalized_slot}.",
            suffix=".tmp",
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


def list_saves(save_dir: Path | None = None) -> list[str]:
    base = save_dir or DEFAULT_SAVE_DIR
    if not base.exists():
        return []

    slots: list[str] = []
    for path in base.glob("*.json"):
        if path.is_file() and _SLOT_PATTERN.match(path.stem):
            slots.append(path.stem)
    return sorted(slots)
