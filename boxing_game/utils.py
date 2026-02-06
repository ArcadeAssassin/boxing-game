"""Shared utility helpers used across boxing-game modules.

Centralises small clamping / validation primitives that were previously
duplicated in individual engine modules.
"""

from __future__ import annotations


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    """Clamp *value* to the inclusive ``[minimum, maximum]`` range."""
    return max(minimum, min(maximum, int(value)))


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    """Clamp *value* to the inclusive ``[minimum, maximum]`` range."""
    return max(minimum, min(maximum, float(value)))


def clamp_stat(value: int, *, lower: int = 20, upper: int = 95) -> int:
    """Clamp a boxer stat to the default ``[20, 95]`` range.

    The bounds can be overridden for special cases (e.g. aging model
    brackets that use different limits).
    """
    return max(lower, min(upper, int(value)))


def clamp_probability(value: object, default: float) -> float:
    """Parse *value* as a float and clamp it to ``[0.0, 1.0]``.

    Returns *default* (also clamped) if *value* cannot be converted.
    """
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return max(0.0, min(1.0, default))
    return max(0.0, min(1.0, numeric))


def coerce_int(value: object) -> int | None:
    """Safely coerce *value* to ``int``, returning ``None`` on failure."""
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
