"""Pro money management: camps, medical recovery, and staff upgrades.

Provides money-driven gameplay systems that unlock after turning pro.
Staff passives influence training quality, wear reduction, rest
recovery, and aging outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

from boxing_game.constants import MAX_FATIGUE, MAX_INJURY_RISK
from boxing_game.models import CareerState, Stats
from boxing_game.modules.attribute_engine import training_gain
from boxing_game.rules_registry import load_rule_set
from boxing_game.utils import clamp_int


@dataclass(frozen=True)
class StaffUpgradeOption:
    """A single staff member that can be upgraded."""

    key: str
    label: str
    level: int
    max_level: int
    next_cost: float | None


# ---------------------------------------------------------------------------
# Rules access
# ---------------------------------------------------------------------------

def _pro_spending_rules() -> dict:
    return load_rule_set("pro_spending")


# ---------------------------------------------------------------------------
# Staff level management
# ---------------------------------------------------------------------------

def ensure_staff_levels(state: CareerState) -> None:
    """Backfill missing staff keys with level 0."""
    cfg = _pro_spending_rules()["staff_upgrades"]
    if not isinstance(state.pro_career.staff_levels, dict):
        state.pro_career.staff_levels = {}
    for staff_key in cfg.keys():
        if staff_key not in state.pro_career.staff_levels:
            state.pro_career.staff_levels[staff_key] = 0
        else:
            state.pro_career.staff_levels[staff_key] = max(
                0, int(state.pro_career.staff_levels[staff_key])
            )


def _staff_level(state: CareerState, staff_key: str) -> int:
    ensure_staff_levels(state)
    return int(state.pro_career.staff_levels.get(staff_key, 0))


def staff_summary_lines(state: CareerState) -> list[str]:
    """Return human-readable lines describing each staff member's level."""
    ensure_staff_levels(state)
    rules = _pro_spending_rules()["staff_upgrades"]
    lines: list[str] = []
    for staff_key, cfg in rules.items():
        label = str(cfg.get("label", staff_key))
        level = _staff_level(state, staff_key)
        max_level = int(cfg.get("max_level", len(cfg.get("cost_by_level", []))))
        lines.append(f"{label}: L{level}/{max_level}")
    return lines


def list_staff_upgrade_options(state: CareerState) -> list[StaffUpgradeOption]:
    """Return all available staff upgrades with their current level and cost."""
    ensure_staff_levels(state)
    rules = _pro_spending_rules()["staff_upgrades"]
    options: list[StaffUpgradeOption] = []
    for staff_key, cfg in rules.items():
        level = _staff_level(state, staff_key)
        max_level = int(cfg.get("max_level", len(cfg.get("cost_by_level", []))))
        costs = [float(item) for item in cfg.get("cost_by_level", [])]
        next_cost = costs[level] if level < max_level and level < len(costs) else None
        options.append(
            StaffUpgradeOption(
                key=str(staff_key),
                label=str(cfg.get("label", staff_key)),
                level=level,
                max_level=max_level,
                next_cost=next_cost,
            )
        )
    return options


# ---------------------------------------------------------------------------
# Staff passive bonuses
# ---------------------------------------------------------------------------

def _elite_coach_bonus(state: CareerState) -> int:
    if not state.pro_career.is_active:
        return 0
    rules = _pro_spending_rules()["staff_upgrades"]["elite_coach"]
    level = _staff_level(state, "elite_coach")
    return max(0, level * int(rules.get("training_focus_bonus_per_level", 0)))


def _nutritionist_level(state: CareerState) -> int:
    if not state.pro_career.is_active:
        return 0
    return _staff_level(state, "nutritionist")


def adjusted_fatigue_gain(state: CareerState, base_gain: int) -> int:
    """Return fatigue gain after nutritionist passive reduction."""
    gain = int(base_gain)
    if gain <= 0:
        return 0
    rules = _pro_spending_rules()["staff_upgrades"]["nutritionist"]
    reduction = _nutritionist_level(state) * int(rules.get("fatigue_gain_reduction_per_level", 0))
    return max(0, gain - reduction)


def adjusted_injury_risk_gain(state: CareerState, base_gain: int) -> int:
    """Return injury-risk gain after nutritionist passive reduction."""
    gain = int(base_gain)
    if gain <= 0:
        return 0
    rules = _pro_spending_rules()["staff_upgrades"]["nutritionist"]
    reduction = _nutritionist_level(state) * int(rules.get("injury_risk_gain_reduction_per_level", 0))
    return max(0, gain - reduction)


def _rest_fatigue_bonus(state: CareerState) -> int:
    rules = _pro_spending_rules()["staff_upgrades"]["nutritionist"]
    return _nutritionist_level(state) * int(rules.get("rest_recovery_bonus_per_level", 0))


def _rest_injury_bonus(state: CareerState) -> int:
    rules = _pro_spending_rules()["staff_upgrades"]["nutritionist"]
    return _nutritionist_level(state) * int(rules.get("injury_risk_rest_bonus_per_level", 0))


def age_decline_reduction_factor(state: CareerState) -> float:
    """Return the aging-decline multiplier provided by sports-science staff."""
    if not state.pro_career.is_active:
        return 1.0
    rules = _pro_spending_rules()["staff_upgrades"].get("sports_science", {})
    level = _staff_level(state, "sports_science")
    per_level = float(rules.get("age_decline_reduction_per_level", 0.0))
    return max(0.55, min(1.0, 1.0 - (level * per_level)))


def age_iq_growth_bonus_factor(state: CareerState) -> float:
    """Return the ring-IQ growth bonus multiplier from sports-science staff."""
    if not state.pro_career.is_active:
        return 1.0
    rules = _pro_spending_rules()["staff_upgrades"].get("sports_science", {})
    level = _staff_level(state, "sports_science")
    per_level = float(rules.get("ring_iq_growth_bonus_per_level", 0.0))
    return max(1.0, 1.0 + (level * per_level))


# ---------------------------------------------------------------------------
# Focus training helpers
# ---------------------------------------------------------------------------

def _add_focus_points(stats: Stats, focus: str, amount: int) -> Stats:
    if amount <= 0:
        return stats
    fields = stats.to_dict()
    if focus not in fields:
        raise ValueError(f"Unknown focus area: {focus}")
    limits = load_rule_set("attribute_model")["stat_limits"]
    max_stat = int(limits["max"])
    fields[focus] = min(max_stat, fields[focus] + int(amount))
    return Stats.from_dict(fields)


# ---------------------------------------------------------------------------
# Monthly actions
# ---------------------------------------------------------------------------

def apply_standard_training(state: CareerState, focus: str) -> dict[str, int]:
    """Apply one month of standard training on *focus*, returning details."""
    state.boxer.stats = training_gain(state.boxer.stats, focus)

    coach_bonus = _elite_coach_bonus(state)
    state.boxer.stats = _add_focus_points(state.boxer.stats, focus, coach_bonus)

    fatigue_gain = adjusted_fatigue_gain(state, 1)
    state.boxer.fatigue = clamp_int(state.boxer.fatigue + fatigue_gain, 0, MAX_FATIGUE)

    injury_gain = adjusted_injury_risk_gain(state, 2)
    state.boxer.injury_risk = clamp_int(state.boxer.injury_risk + injury_gain, 0, MAX_INJURY_RISK)

    return {
        "coach_bonus": coach_bonus,
        "fatigue_gain": fatigue_gain,
        "injury_risk_gain": injury_gain,
    }


def apply_rest_month(state: CareerState) -> dict[str, int]:
    """Apply one month of rest, returning fatigue/injury reductions."""
    fatigue_reduction = 3 + _rest_fatigue_bonus(state)
    injury_reduction = 3 + _rest_injury_bonus(state)

    before_fatigue = state.boxer.fatigue
    before_injury = state.boxer.injury_risk

    state.boxer.fatigue = clamp_int(before_fatigue - fatigue_reduction, 0, MAX_FATIGUE)
    state.boxer.injury_risk = clamp_int(before_injury - injury_reduction, 0, MAX_INJURY_RISK)

    return {
        "fatigue_reduced": before_fatigue - state.boxer.fatigue,
        "injury_risk_reduced": before_injury - state.boxer.injury_risk,
    }


def special_training_camp(state: CareerState, focus: str) -> dict[str, int | float]:
    """Run a paid special training camp (pro only), returning details."""
    if not state.pro_career.is_active:
        raise ValueError("Special training camp is available only after turning pro.")

    rules = _pro_spending_rules()["special_camp"]
    cost = float(rules["cost"])
    if state.pro_career.purse_balance < cost:
        raise ValueError("Insufficient purse balance for special training camp.")

    cycles = max(1, int(rules.get("training_cycles", 2)))
    for _ in range(cycles):
        state.boxer.stats = training_gain(state.boxer.stats, focus)

    coach_bonus = _elite_coach_bonus(state) * int(rules.get("coach_bonus_multiplier", 1))
    state.boxer.stats = _add_focus_points(state.boxer.stats, focus, coach_bonus)

    fatigue_gain = adjusted_fatigue_gain(state, int(rules.get("fatigue_gain", 3)))
    state.boxer.fatigue = clamp_int(state.boxer.fatigue + fatigue_gain, 0, MAX_FATIGUE)

    injury_gain = adjusted_injury_risk_gain(state, int(rules.get("injury_risk_gain", 5)))
    state.boxer.injury_risk = clamp_int(state.boxer.injury_risk + injury_gain, 0, MAX_INJURY_RISK)

    state.pro_career.purse_balance = max(0.0, state.pro_career.purse_balance - cost)

    return {
        "cost": round(cost, 2),
        "coach_bonus": coach_bonus,
        "fatigue_gain": fatigue_gain,
        "injury_risk_gain": injury_gain,
        "months": max(0, int(rules.get("months", 1))),
    }


def medical_recovery(state: CareerState) -> dict[str, int | float]:
    """Run a paid medical recovery programme (pro only), returning details."""
    if not state.pro_career.is_active:
        raise ValueError("Medical recovery is available only after turning pro.")

    rules = _pro_spending_rules()["medical_recovery"]
    cost = float(rules["cost"])
    if state.pro_career.purse_balance < cost:
        raise ValueError("Insufficient purse balance for medical recovery.")

    fatigue_reduction = max(0, int(rules.get("fatigue_reduction", 6)))
    injury_reduction = max(0, int(rules.get("injury_risk_reduction", 14)))
    months = max(0, int(rules.get("months", 1)))

    before_fatigue = state.boxer.fatigue
    before_injury = state.boxer.injury_risk

    state.boxer.fatigue = clamp_int(before_fatigue - fatigue_reduction, 0, MAX_FATIGUE)
    state.boxer.injury_risk = clamp_int(before_injury - injury_reduction, 0, MAX_INJURY_RISK)
    state.pro_career.purse_balance = max(0.0, state.pro_career.purse_balance - cost)

    return {
        "cost": round(cost, 2),
        "fatigue_reduced": before_fatigue - state.boxer.fatigue,
        "injury_risk_reduced": before_injury - state.boxer.injury_risk,
        "months": months,
    }


def purchase_staff_upgrade(state: CareerState, staff_key: str) -> dict[str, int | float | str]:
    """Purchase the next level for *staff_key* (pro only)."""
    if not state.pro_career.is_active:
        raise ValueError("Staff upgrades are available only after turning pro.")

    rules = _pro_spending_rules()["staff_upgrades"]
    if staff_key not in rules:
        raise ValueError(f"Unknown staff upgrade: {staff_key}")

    ensure_staff_levels(state)
    cfg = rules[staff_key]
    label = str(cfg.get("label", staff_key))
    level = _staff_level(state, staff_key)
    max_level = int(cfg.get("max_level", len(cfg.get("cost_by_level", []))))

    if level >= max_level:
        raise ValueError(f"{label} is already at max level.")

    costs = [float(item) for item in cfg.get("cost_by_level", [])]
    if level >= len(costs):
        raise ValueError(f"{label} has no configured cost for next level.")

    cost = costs[level]
    if state.pro_career.purse_balance < cost:
        raise ValueError(f"Insufficient purse balance for {label} upgrade.")

    state.pro_career.purse_balance = max(0.0, state.pro_career.purse_balance - cost)
    state.pro_career.staff_levels[staff_key] = level + 1

    return {
        "key": staff_key,
        "label": label,
        "old_level": level,
        "new_level": level + 1,
        "max_level": max_level,
        "cost": round(cost, 2),
    }
