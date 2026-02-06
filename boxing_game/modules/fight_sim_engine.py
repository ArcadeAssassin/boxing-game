"""Round-based fight simulation for amateur and pro bouts.

Simulates each round with form calculations, judge scoring, and
stoppage (KO/TKO) chances.  Uses configurable fight models from
``rules/fight_model.json``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from boxing_game.models import Boxer, FightResult, Opponent, Stats
from boxing_game.modules.experience_engine import boxer_experience_profile, opponent_experience_profile
from boxing_game.rules_registry import load_rule_set


@dataclass
class _JudgeCard:
    """Accumulates scorecard points for one judge."""

    boxer_points: int = 0
    opponent_points: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _weighted_skill(stats: Stats, weights: dict[str, float]) -> float:
    """Compute a composite skill score from *stats* using *weights*."""
    values = stats.to_dict()
    total = 0.0
    for key, weight in weights.items():
        total += values[key] * float(weight)
    return total


def _check_stoppage(
    round_margin: float,
    boxer_ko_chance: float,
    opp_ko_chance: float,
    randomizer: random.Random,
    *,
    boxer_name: str,
    opponent_name: str,
    round_number: int,
    round_log: list[str],
    threshold: float,
) -> FightResult | None:
    """Return a ``FightResult`` if a stoppage occurs, otherwise ``None``."""
    if round_margin > threshold and randomizer.random() < boxer_ko_chance:
        round_log.append(
            f"R{round_number}: {boxer_name} lands clean and forces a stoppage."
        )
        return FightResult(
            winner=boxer_name, method="TKO",
            rounds_completed=round_number, scorecards=[], round_log=round_log,
        )
    if round_margin < -threshold and randomizer.random() < opp_ko_chance:
        round_log.append(
            f"R{round_number}: {opponent_name} breaks through and scores a stoppage."
        )
        return FightResult(
            winner=opponent_name, method="TKO",
            rounds_completed=round_number, scorecards=[], round_log=round_log,
        )
    return None


def _score_round(
    round_margin: float,
    judge_cards: list[_JudgeCard],
    judge_noise: float,
    randomizer: random.Random,
) -> None:
    """Update judge cards for one round based on *round_margin*."""
    for card in judge_cards:
        noisy_margin = round_margin + randomizer.gauss(0, judge_noise)
        if noisy_margin > 1.0:
            card.boxer_points += 10
            card.opponent_points += 9
        elif noisy_margin < -1.0:
            card.boxer_points += 9
            card.opponent_points += 10
        else:
            card.boxer_points += 10
            card.opponent_points += 10


def _decision_from_cards(
    judge_cards: list[_JudgeCard],
    boxer_name: str,
    opponent_name: str,
    scheduled_rounds: int,
) -> FightResult:
    """Compile judge cards into a decision result."""
    boxer_judges = 0
    opponent_judges = 0
    draw_judges = 0
    scorecards: list[str] = []

    for card in judge_cards:
        scorecards.append(f"{card.boxer_points}-{card.opponent_points}")
        if card.boxer_points > card.opponent_points:
            boxer_judges += 1
        elif card.opponent_points > card.boxer_points:
            opponent_judges += 1
        else:
            draw_judges += 1

    if boxer_judges > opponent_judges:
        winner = boxer_name
    elif opponent_judges > boxer_judges:
        winner = opponent_name
    else:
        winner = "Draw"

    if winner == "Draw":
        method = "DRAW"
    elif draw_judges > 0 and max(boxer_judges, opponent_judges) >= 2:
        method = "MD"
    elif boxer_judges == 3 or opponent_judges == 3:
        method = "UD"
    else:
        method = "SD"

    return FightResult(
        winner=winner, method=method,
        rounds_completed=scheduled_rounds, scorecards=scorecards,
        round_log=[],  # populated by caller
    )


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def _simulate_with_model(
    boxer: Boxer,
    opponent: Opponent,
    model_key: str,
    rounds: int | None = None,
    rng: random.Random | None = None,
) -> FightResult:
    """Simulate a full fight using the specified fight model."""
    randomizer = rng or random.Random()

    models = load_rule_set("fight_model")
    if model_key not in models:
        raise ValueError(f"Unknown fight model: {model_key}")
    model = models[model_key]
    style_weights = model["style_weights"]
    scheduled_rounds = int(model["rounds"]) if rounds is None else int(rounds)
    if scheduled_rounds < 1:
        raise ValueError("Rounds must be >= 1.")

    swing_factor = float(model["swing_factor"])
    judge_noise = float(model["judge_noise"])
    base_ko_chance = float(model["base_ko_chance"])
    max_ko_chance = float(model["max_ko_chance"])
    stamina_decay = float(model["stamina_decay_per_round"])
    fatigue_penalty = float(model["fatigue_penalty_per_point"])
    injury_risk_penalty = float(model.get("injury_risk_penalty_per_point", 0.0))
    stoppage_threshold = float(model.get("stoppage_margin_threshold", 3.2))

    boxer_base_skill = _weighted_skill(boxer.stats, style_weights)
    opponent_base_skill = _weighted_skill(opponent.stats, style_weights)
    boxer_experience_bonus = boxer_experience_profile(boxer).fight_bonus
    opponent_experience_bonus = opponent_experience_profile(opponent).fight_bonus

    judge_cards = [_JudgeCard(), _JudgeCard(), _JudgeCard()]
    round_log: list[str] = []

    boxer_fatigue = float(boxer.fatigue)
    opponent_fatigue = 0.0

    for round_number in range(1, scheduled_rounds + 1):
        boxer_form = (
            boxer_base_skill + boxer_experience_bonus
            - (boxer_fatigue * fatigue_penalty)
            - (boxer.injury_risk * injury_risk_penalty)
        )
        opponent_form = (
            opponent_base_skill + opponent_experience_bonus
            - (opponent_fatigue * fatigue_penalty)
        )

        boxer_swing = randomizer.gauss(0, swing_factor)
        opponent_swing = randomizer.gauss(0, swing_factor)
        round_margin = (boxer_form + boxer_swing) - (opponent_form + opponent_swing)

        # KO / stoppage chances
        power_edge = boxer.stats.power - opponent.stats.chin
        opp_power_edge = opponent.stats.power - boxer.stats.chin
        ko_pressure = max(0.0, (abs(round_margin) - 6.0) * 0.012)

        boxer_ko_chance = min(max_ko_chance, max(0.0, base_ko_chance + ko_pressure + (power_edge * 0.002)))
        opp_ko_chance = min(max_ko_chance, max(0.0, base_ko_chance + ko_pressure + (opp_power_edge * 0.002)))

        stoppage = _check_stoppage(
            round_margin, boxer_ko_chance, opp_ko_chance, randomizer,
            boxer_name=boxer.profile.name, opponent_name=opponent.name,
            round_number=round_number, round_log=round_log,
            threshold=stoppage_threshold,
        )
        if stoppage is not None:
            return stoppage

        # Round narration
        if round_margin > 1.2:
            round_winner = boxer.profile.name
            notes = f"{boxer.profile.name} controls distance"
        elif round_margin < -1.2:
            round_winner = opponent.name
            notes = f"{opponent.name} wins exchanges inside"
        else:
            round_winner = "even"
            notes = "close tactical round"

        _score_round(round_margin, judge_cards, judge_noise, randomizer)
        round_log.append(f"R{round_number}: {notes} ({round_winner})")

        boxer_fatigue += stamina_decay
        opponent_fatigue += stamina_decay

    # Decision
    decision = _decision_from_cards(
        judge_cards, boxer.profile.name, opponent.name, scheduled_rounds,
    )
    return FightResult(
        winner=decision.winner,
        method=decision.method,
        rounds_completed=decision.rounds_completed,
        scorecards=decision.scorecards,
        round_log=round_log,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate_amateur_fight(
    boxer: Boxer,
    opponent: Opponent,
    rounds: int | None = None,
    rng: random.Random | None = None,
) -> FightResult:
    """Simulate an amateur fight using the ``amateur`` fight model."""
    return _simulate_with_model(boxer, opponent, "amateur", rounds=rounds, rng=rng)


def simulate_pro_fight(
    boxer: Boxer,
    opponent: Opponent,
    rounds: int | None = None,
    rng: random.Random | None = None,
) -> FightResult:
    """Simulate a pro fight using the ``pro`` fight model."""
    return _simulate_with_model(boxer, opponent, "pro", rounds=rounds, rng=rng)
