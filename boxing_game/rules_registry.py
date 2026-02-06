from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = PROJECT_ROOT / "rules"


@lru_cache(maxsize=32)
def load_rule_set(name: str) -> dict[str, Any]:
    path = RULES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Rule set not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
