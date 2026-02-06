from __future__ import annotations

import random
from dataclasses import dataclass

from boxing_game.models import Boxer, FightResult, Opponent, Stats
from boxing_game.modules.experience_engine import boxer_experience_profile, opponent_experience_profile
from boxing_game.rules_registry import load_rule_set


@dataclass
class _JudgeCard:
    boxer_points: int = 0
    opponent_points: int = 0


def _weighted_skill(stats: Stats, weights: dict[str, float]) -> float:
    values = stats.to_dict()
    total = 0.0
    for key, weight in weights.items():
        total += values[key] * float(weight)
    return total


def _simulate_with_model(
    boxer: Boxer,
    opponent: Opponent,
    model_key: str,
    rounds: int | None = None,
    rng: random.Random | None = None,
) -> FightResult:
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
            boxer_base_skill
            + boxer_experience_bonus
            - (boxer_fatigue * fatigue_penalty)
        )
        opponent_form = (
            opponent_base_skill
            + opponent_experience_bonus
            - (opponent_fatigue * fatigue_penalty)
        )

        boxer_swing = randomizer.gauss(0, swing_factor)
        opponent_swing = randomizer.gauss(0, swing_factor)
        round_margin = (boxer_form + boxer_swing) - (opponent_form + opponent_swing)

        power_edge = boxer.stats.power - opponent.stats.chin
        opp_power_edge = opponent.stats.power - boxer.stats.chin
        ko_pressure = max(0.0, (abs(round_margin) - 6.0) * 0.012)

        boxer_ko_chance = min(
            max_ko_chance,
            max(0.0, base_ko_chance + ko_pressure + (power_edge * 0.002)),
        )
        opp_ko_chance = min(
            max_ko_chance,
            max(0.0, base_ko_chance + ko_pressure + (opp_power_edge * 0.002)),
        )

        if round_margin > 3.2 and randomizer.random() < boxer_ko_chance:
            round_log.append(
                f"R{round_number}: {boxer.profile.name} lands clean and forces a stoppage."
            )
            return FightResult(
                winner=boxer.profile.name,
                method="TKO",
                rounds_completed=round_number,
                scorecards=[],
                round_log=round_log,
            )

        if round_margin < -3.2 and randomizer.random() < opp_ko_chance:
            round_log.append(
                f"R{round_number}: {opponent.name} breaks through and scores a stoppage."
            )
            return FightResult(
                winner=opponent.name,
                method="TKO",
                rounds_completed=round_number,
                scorecards=[],
                round_log=round_log,
            )

        if round_margin > 1.2:
            round_winner = boxer.profile.name
            notes = f"{boxer.profile.name} controls distance"
        elif round_margin < -1.2:
            round_winner = opponent.name
            notes = f"{opponent.name} wins exchanges inside"
        else:
            round_winner = "even"
            notes = "close tactical round"

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

        round_log.append(f"R{round_number}: {notes} ({round_winner})")

        boxer_fatigue += stamina_decay
        opponent_fatigue += stamina_decay

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
        winner = boxer.profile.name
    elif opponent_judges > boxer_judges:
        winner = opponent.name
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
        winner=winner,
        method=method,
        rounds_completed=scheduled_rounds,
        scorecards=scorecards,
        round_log=round_log,
    )


def simulate_amateur_fight(
    boxer: Boxer,
    opponent: Opponent,
    rounds: int | None = None,
    rng: random.Random | None = None,
) -> FightResult:
    return _simulate_with_model(boxer, opponent, "amateur", rounds=rounds, rng=rng)


def simulate_pro_fight(
    boxer: Boxer,
    opponent: Opponent,
    rounds: int | None = None,
    rng: random.Random | None = None,
) -> FightResult:
    return _simulate_with_model(boxer, opponent, "pro", rounds=rounds, rng=rng)
