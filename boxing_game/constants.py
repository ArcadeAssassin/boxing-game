"""Shared game constants.

Centralises magic numbers and string literals that are referenced by
multiple modules so they have a single source of truth.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Age
# ---------------------------------------------------------------------------
STARTING_AGE: int = 15
"""Default starting age for newly created boxers."""

# ---------------------------------------------------------------------------
# Sanctioning organisations
# ---------------------------------------------------------------------------
ORGANIZATION_NAMES: tuple[str, ...] = ("WBC", "WBA", "IBF", "WBO")
"""Canonical sanctioning-body names displayed in rankings and fight offers."""

# ---------------------------------------------------------------------------
# Stat boundaries
# ---------------------------------------------------------------------------
MIN_STAT: int = 20
"""Absolute minimum for any single boxer stat."""

MAX_STAT: int = 95
"""Absolute maximum for any single boxer stat (before aging override)."""

# ---------------------------------------------------------------------------
# Fatigue / injury caps
# ---------------------------------------------------------------------------
MAX_FATIGUE: int = 12
"""Maximum fatigue a boxer can accumulate."""

MAX_INJURY_RISK: int = 100
"""Maximum injury-risk a boxer can accumulate."""

# ---------------------------------------------------------------------------
# Save system
# ---------------------------------------------------------------------------
CURRENT_SAVE_VERSION: int = 2
"""Serialised save-file format version."""
