"""Deterministic boxer aging-profile generation.

Generates a stable ``AgingProfile`` from boxer identity and body metrics.
The profile determines peak age, decline onset, decline severity, and
ring-IQ growth factor for the career-clock birthday system.
"""

from __future__ import annotations

import random

from boxing_game.models import AgingProfile
from boxing_game.utils import clamp_float, clamp_int


def generate_aging_profile(
    *,
    name: str,
    stance: str,
    height_inches: int,
    weight_lbs: int,
) -> AgingProfile:
    """Create a deterministic aging profile seeded from identity/body metrics.

    The seed ensures the same boxer always receives the same profile
    regardless of when or how many times the function is called.
    """
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

    peak_age = clamp_int(
        randomizer.randint(26, 30) + weight_bias + frame_bias, 24, 34,
    )
    decline_onset_age = clamp_int(
        peak_age + randomizer.randint(1, 3), peak_age, 40,
    )
    decline_severity = round(
        clamp_float(randomizer.uniform(0.85, 1.18), 0.7, 1.4), 3,
    )
    iq_growth_factor = round(
        clamp_float(randomizer.uniform(0.9, 1.2), 0.75, 1.35), 3,
    )

    return AgingProfile(
        peak_age=peak_age,
        decline_onset_age=decline_onset_age,
        decline_severity=decline_severity,
        iq_growth_factor=iq_growth_factor,
    )
