from __future__ import annotations

import random

from boxing_game.models import AgingProfile


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def generate_aging_profile(
    *,
    name: str,
    stance: str,
    height_inches: int,
    weight_lbs: int,
) -> AgingProfile:
    # Deterministic seed so profile is stable across runs and legacy migrations.
    seed = f"{name.strip().lower()}:{stance.strip().lower()}:{height_inches}:{weight_lbs}"
    randomizer = random.Random(seed)

    weight_bias = 0
    if weight_lbs >= 175:
        weight_bias += 1
    if weight_lbs >= 200:
        weight_bias += 1

    frame_bias = 0
    if height_inches >= 74:
        frame_bias += 1

    peak_age = randomizer.randint(26, 30) + weight_bias + frame_bias
    peak_age = _clamp_int(peak_age, 24, 34)

    decline_onset_age = peak_age + randomizer.randint(1, 3)
    decline_onset_age = _clamp_int(decline_onset_age, peak_age, 40)

    decline_severity = round(randomizer.uniform(0.85, 1.18), 3)
    iq_growth_factor = round(randomizer.uniform(0.9, 1.2), 3)

    decline_severity = round(_clamp_float(decline_severity, 0.7, 1.4), 3)
    iq_growth_factor = round(_clamp_float(iq_growth_factor, 0.75, 1.35), 3)

    return AgingProfile(
        peak_age=peak_age,
        decline_onset_age=decline_onset_age,
        decline_severity=decline_severity,
        iq_growth_factor=iq_growth_factor,
    )
