#!/usr/bin/env python3
"""Career pacing simulation for realism calibration.

Real-life anchors used for comparison:
- Active pros in a prospective cohort averaged about 2.7 bouts/year.
- Another cohort of professionals reported ~1.7-2.0 bouts/year depending on sample.

This script models game careers with training/rest decisions and reports whether
pro fight cadence is inside that broad real-life active range.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path


def _bootstrap_project_path() -> None:
    root = Path(__file__).resolve().parents[1]
    candidate = str(root)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


_bootstrap_project_path()

from boxing_game.models import CareerState
from boxing_game.modules.amateur_circuit import apply_fight_result, generate_opponent, pro_ready
from boxing_game.modules.career_clock import advance_month
from boxing_game.modules.fight_sim_engine import simulate_amateur_fight, simulate_pro_fight
from boxing_game.modules.player_profile import create_boxer
from boxing_game.modules.pro_career import (
    apply_pro_fight_result,
    generate_pro_opponent,
    offer_purse,
    turn_pro,
)
from boxing_game.modules.pro_spending import (
    apply_rest_month,
    apply_standard_training,
    medical_recovery,
    purchase_staff_upgrade,
)

# Broad active-pro benchmark band from published cohorts.
REAL_WORLD_PRO_BOUTS_PER_YEAR_MIN = 1.7
REAL_WORLD_PRO_BOUTS_PER_YEAR_MAX = 2.7


@dataclass(frozen=True)
class CareerSample:
    turn_pro_age: int | None
    amateur_fights: int
    pro_fights: int
    total_fights: int
    pro_fights_per_year: float
    pro_win_pct: float


def _targeted_focus(state: CareerState) -> str:
    # Train weakest of the core ring-performance stats.
    priority = ("stamina", "defense", "ring_iq", "speed", "power", "chin")
    values = state.boxer.stats.to_dict()
    return min(priority, key=lambda key: values[key])


def simulate_career(
    seed: int,
    *,
    retire_age: int,
    targeted_training: bool,
) -> CareerSample:
    rng = random.Random(seed)
    boxer = create_boxer(
        name=f"Sim {seed}",
        stance=rng.choice(("orthodox", "southpaw")),
        height_ft=5,
        height_in=10,
        weight_lbs=147,
    )
    state = CareerState(boxer=boxer)

    turn_pro_age: int | None = None
    last_pro_fight_month = -999
    training_months_since_last_pro_fight = 0

    while state.boxer.profile.age < retire_age:
        if not state.pro_career.is_active and pro_ready(state):
            turn_pro(state, rng=rng)
            turn_pro_age = state.boxer.profile.age
            continue

        if not state.pro_career.is_active:
            if state.boxer.fatigue >= 6 or state.boxer.injury_risk >= 26:
                apply_rest_month(state)
                advance_month(state, 1)
                continue

            should_train = (state.career_months % 3 == 1) and state.boxer.fatigue <= 7
            if should_train:
                focus = _targeted_focus(state) if targeted_training else rng.choice(
                    ("speed", "ring_iq", "stamina", "defense")
                )
                apply_standard_training(state, focus)
                advance_month(state, 1)
                continue

            opponent = generate_opponent(state, rng=rng)
            result = simulate_amateur_fight(state.boxer, opponent, rounds=3, rng=rng)
            apply_fight_result(state, opponent, result)
            advance_month(state, 1)
            continue

        # Pro phase: buy basic staff when affordable.
        if state.pro_career.staff_levels.get("nutritionist", 0) < 1:
            try:
                purchase_staff_upgrade(state, "nutritionist")
            except ValueError:
                pass
        if state.pro_career.staff_levels.get("elite_coach", 0) < 1:
            try:
                purchase_staff_upgrade(state, "elite_coach")
            except ValueError:
                pass

        months_since_fight = state.career_months - last_pro_fight_month

        if state.boxer.injury_risk >= 45 and state.pro_career.purse_balance >= 1800:
            try:
                medical_recovery(state)
                advance_month(state, 1)
                continue
            except ValueError:
                pass

        if state.boxer.fatigue >= 7 or state.boxer.injury_risk >= 34:
            apply_rest_month(state)
            training_months_since_last_pro_fight = max(
                0, training_months_since_last_pro_fight - 1
            )
            advance_month(state, 1)
            continue

        should_fight = (
            training_months_since_last_pro_fight >= 1
            and (
                (
                    months_since_fight >= 3
                    and state.boxer.fatigue <= 5
                    and state.boxer.injury_risk <= 24
                )
                or months_since_fight >= 5
            )
        )
        if should_fight:
            opponent = generate_pro_opponent(state, rng=rng)
            purse = offer_purse(state, opponent, rng=rng)
            result = simulate_pro_fight(state.boxer, opponent, rounds=8, rng=rng)
            apply_pro_fight_result(state, opponent, result, purse)
            last_pro_fight_month = state.career_months
            training_months_since_last_pro_fight = 0
            advance_month(state, 1)
            continue

        focus = _targeted_focus(state) if targeted_training else rng.choice(
            ("speed", "stamina", "defense", "ring_iq", "power")
        )
        apply_standard_training(state, focus)
        training_months_since_last_pro_fight += 1
        advance_month(state, 1)

    amateur_record = state.boxer.record
    pro_record = state.pro_career.record
    amateur_fights = amateur_record.wins + amateur_record.losses + amateur_record.draws
    pro_fights = pro_record.wins + pro_record.losses + pro_record.draws
    total_fights = amateur_fights + pro_fights

    if turn_pro_age is None:
        pro_fights_per_year = 0.0
    else:
        pro_years = max(1, retire_age - turn_pro_age)
        pro_fights_per_year = pro_fights / pro_years

    pro_win_pct = 0.0 if pro_fights == 0 else (pro_record.wins / pro_fights)

    return CareerSample(
        turn_pro_age=turn_pro_age,
        amateur_fights=amateur_fights,
        pro_fights=pro_fights,
        total_fights=total_fights,
        pro_fights_per_year=pro_fights_per_year,
        pro_win_pct=pro_win_pct,
    )


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    idx = int((len(values) - 1) * p)
    return sorted(values)[idx]


def summarize(samples: list[CareerSample]) -> dict[str, float]:
    turn_pro_ages = [s.turn_pro_age for s in samples if s.turn_pro_age is not None]
    amateurs = [s.amateur_fights for s in samples]
    pros = [s.pro_fights for s in samples]
    totals = [s.total_fights for s in samples]
    ppy = [s.pro_fights_per_year for s in samples]
    win_pct = [s.pro_win_pct for s in samples]
    return {
        "turn_pro_age_avg": statistics.mean(turn_pro_ages),
        "turn_pro_age_median": statistics.median(turn_pro_ages),
        "amateur_avg": statistics.mean(amateurs),
        "pro_avg": statistics.mean(pros),
        "total_avg": statistics.mean(totals),
        "total_p10": _percentile(totals, 0.1),
        "total_p90": _percentile(totals, 0.9),
        "pro_fights_per_year_avg": statistics.mean(ppy),
        "pro_fights_per_year_p10": _percentile(ppy, 0.1),
        "pro_fights_per_year_p90": _percentile(ppy, 0.9),
        "pro_win_pct_avg": statistics.mean(win_pct),
    }


def _print_report(label: str, report: dict[str, float]) -> None:
    avg_ppy = report["pro_fights_per_year_avg"]
    in_range = (
        REAL_WORLD_PRO_BOUTS_PER_YEAR_MIN
        <= avg_ppy
        <= REAL_WORLD_PRO_BOUTS_PER_YEAR_MAX
    )

    print(f"\n== {label} ==")
    print(
        "Turn pro age "
        f"avg {report['turn_pro_age_avg']:.2f} | "
        f"median {report['turn_pro_age_median']:.0f}"
    )
    print(
        "Fights "
        f"amateur {report['amateur_avg']:.2f} | "
        f"pro {report['pro_avg']:.2f} | "
        f"total {report['total_avg']:.2f} "
        f"(p10={report['total_p10']:.0f}, p90={report['total_p90']:.0f})"
    )
    print(
        "Pro bouts/year "
        f"avg {avg_ppy:.2f} "
        f"(p10={report['pro_fights_per_year_p10']:.2f}, "
        f"p90={report['pro_fights_per_year_p90']:.2f})"
    )
    print(f"Pro win% avg {report['pro_win_pct_avg']:.3f}")
    print(
        "Real-life active benchmark "
        f"{REAL_WORLD_PRO_BOUTS_PER_YEAR_MIN:.1f}-{REAL_WORLD_PRO_BOUTS_PER_YEAR_MAX:.1f} bouts/year: "
        f"{'IN RANGE' if in_range else 'OUT OF RANGE'}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run career pacing simulations.")
    parser.add_argument(
        "--runs",
        type=int,
        default=300,
        help="Number of deterministic seeds to run per scenario (default: 300).",
    )
    parser.add_argument(
        "--retire-age",
        type=int,
        default=35,
        help="Career end age for simulation horizon (default: 35).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.runs < 10:
        raise SystemExit("--runs must be >= 10")
    if args.retire_age < 22:
        raise SystemExit("--retire-age must be >= 22")

    seeds = range(args.runs)

    baseline = [
        simulate_career(seed, retire_age=args.retire_age, targeted_training=False)
        for seed in seeds
    ]
    targeted = [
        simulate_career(seed, retire_age=args.retire_age, targeted_training=True)
        for seed in seeds
    ]

    print(
        "Career pacing simulation with fatigue, injury risk, and training decisions.\n"
        f"Runs per scenario: {args.runs} | retire age: {args.retire_age}"
    )
    _print_report("Balanced Training", summarize(baseline))
    _print_report("Targeted Training", summarize(targeted))


if __name__ == "__main__":
    main()
