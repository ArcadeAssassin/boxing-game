from __future__ import annotations

from dataclasses import dataclass

from boxing_game.models import Boxer, CareerRecord, FightResult, Opponent
from boxing_game.rules_registry import load_rule_set


@dataclass(frozen=True)
class ExperienceProfile:
    points: int
    level: int
    title: str
    fight_bonus: float
    next_level_points: int | None


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _total_record_fights(record: CareerRecord) -> int:
    return max(0, record.wins + record.losses + record.draws)


def total_career_fights(boxer: Boxer, pro_record: CareerRecord | None = None) -> int:
    total = _total_record_fights(boxer.record)
    if pro_record is not None:
        total += _total_record_fights(pro_record)
    return max(0, total)


def infer_points_from_total_fights(total_fights: int) -> int:
    if total_fights <= 0:
        return 0
    base = int(load_rule_set("experience_model")["base_points_per_fight"]["amateur"])
    return max(0, int(total_fights) * max(1, base))


def _sorted_levels() -> list[dict[str, str | int]]:
    levels = list(load_rule_set("experience_model")["levels"])
    return sorted(
        [
            {
                "name": str(item["name"]),
                "min_points": int(item["min_points"]),
            }
            for item in levels
        ],
        key=lambda item: int(item["min_points"]),
    )


def profile_from_points(points: int) -> ExperienceProfile:
    safe_points = max(0, int(points))
    levels = _sorted_levels()
    if not levels:
        return ExperienceProfile(
            points=safe_points,
            level=1,
            title="newcomer",
            fight_bonus=0.0,
            next_level_points=None,
        )

    selected_index = 0
    for idx, item in enumerate(levels):
        if safe_points >= int(item["min_points"]):
            selected_index = idx
        else:
            break

    selected = levels[selected_index]
    next_level_points: int | None = None
    if selected_index + 1 < len(levels):
        next_level_points = int(levels[selected_index + 1]["min_points"])

    cfg = load_rule_set("experience_model")
    per_level = float(cfg["fight_bonus_per_level"])
    max_bonus = float(cfg["max_fight_bonus"])
    fight_bonus = min(max_bonus, max(0.0, selected_index * per_level))

    return ExperienceProfile(
        points=safe_points,
        level=selected_index + 1,
        title=str(selected["name"]),
        fight_bonus=round(fight_bonus, 2),
        next_level_points=next_level_points,
    )


def boxer_experience_profile(boxer: Boxer, pro_record: CareerRecord | None = None) -> ExperienceProfile:
    points = max(0, int(boxer.experience_points))
    if points == 0:
        fights = total_career_fights(boxer, pro_record=pro_record)
        if fights > 0:
            points = infer_points_from_total_fights(fights)
    return profile_from_points(points)


def opponent_experience_profile(opponent: Opponent) -> ExperienceProfile:
    fights = _total_record_fights(opponent.record)
    points = infer_points_from_total_fights(fights)
    return profile_from_points(points)


def fight_experience_gain(
    *,
    stage: str,
    boxer_name: str,
    opponent_rating: int,
    result: FightResult,
) -> int:
    cfg = load_rule_set("experience_model")
    base_by_stage = {str(k): int(v) for k, v in cfg["base_points_per_fight"].items()}
    if stage not in base_by_stage:
        raise ValueError(f"Unknown experience stage: {stage}")

    result_points = {
        str(key): int(value) for key, value in cfg["result_points"].items()
    }
    if result.winner == boxer_name:
        outcome_key = "win"
    elif result.winner == "Draw":
        outcome_key = "draw"
    else:
        outcome_key = "loss"

    gain = base_by_stage[stage] + result_points[outcome_key]

    rating_scale = float(cfg["rating_bonus_scale"])
    gain += max(0, int(round((int(opponent_rating) - 50) * rating_scale)))

    ko_bonus = int(cfg["ko_bonus"])
    if result.winner == boxer_name and result.method in {"KO", "TKO"}:
        gain += ko_bonus

    max_gain = int(cfg["max_gain_per_fight"])
    return _clamp_int(gain, 1, max_gain)


def add_experience_points(boxer: Boxer, gain: int) -> int:
    applied_gain = max(0, int(gain))
    boxer.experience_points = max(0, int(boxer.experience_points) + applied_gain)
    return applied_gain
