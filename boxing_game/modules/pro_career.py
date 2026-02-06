from __future__ import annotations

import random
from dataclasses import dataclass

from boxing_game.models import (
    CareerRecord,
    CareerState,
    FightHistoryEntry,
    FightResult,
    Opponent,
    ProCareer,
    Stats,
)
from boxing_game.modules.amateur_circuit import FIRST_NAMES, LAST_NAMES, STANCE_CHOICES, pro_ready
from boxing_game.modules.attribute_engine import build_stats
from boxing_game.modules.experience_engine import add_experience_points, fight_experience_gain
from boxing_game.modules.fight_aftermath import calculate_post_fight_impact
from boxing_game.modules.pro_spending import adjusted_fatigue_gain, adjusted_injury_risk_gain
from boxing_game.modules.rating_engine import boxer_overall_rating
from boxing_game.modules.weight_class_engine import WeightClass, classify_weight, list_weight_classes
from boxing_game.rules_registry import load_rule_set


@dataclass(frozen=True)
class RankingEntry:
    rank: int
    name: str
    rating: int
    wins: int
    losses: int
    draws: int
    division: str
    age: int
    stance: str
    p4p_score: float = 0.0
    is_lineal_champion: bool = False
    is_player: bool = False


@dataclass(frozen=True)
class PoundForPoundEntry:
    rank: int
    name: str
    score: float
    rating: int
    division: str
    wins: int
    losses: int
    draws: int
    is_lineal_champion: bool = False
    is_player: bool = False


def _clamp_stat(value: int) -> int:
    return max(20, min(95, value))


def _mean_stat(stats: Stats) -> float:
    values = list(stats.to_dict().values())
    return sum(values) / len(values)


def _organization_names() -> list[str]:
    return [str(item["name"]) for item in load_rule_set("pro_career")["organizations"]]


def _organization_config(name: str) -> dict:
    for item in load_rule_set("pro_career")["organizations"]:
        if str(item["name"]) == name:
            return item
    raise ValueError(f"Unknown organization: {name}")


def _clamp_probability(value: object, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, numeric))


def _sanctioning_policy() -> dict[str, float | int | bool | dict[str, float]]:
    raw = load_rule_set("pro_career").get("sanctioning_policy", {})
    if not isinstance(raw, dict):
        raw = {}

    rank_window = int(raw.get("cross_body_rank_window", 20))
    elite_cutoff = int(raw.get("cross_body_elite_cutoff", 15))
    rank_gap_max = int(raw.get("cross_body_rank_gap_max", 8))
    jitter = int(raw.get("opponent_cross_rank_jitter", 5))
    raw_tier_multipliers = raw.get("tier_probability_multipliers", {})
    tier_probability_multipliers: dict[str, float] = {}
    if isinstance(raw_tier_multipliers, dict):
        for tier_name, multiplier in raw_tier_multipliers.items():
            key = str(tier_name).strip().lower()
            if not key:
                continue
            try:
                tier_probability_multipliers[key] = max(0.25, min(2.0, float(multiplier)))
            except (TypeError, ValueError):
                continue
    if "prospect" not in tier_probability_multipliers:
        tier_probability_multipliers["prospect"] = 1.0
    if "contender" not in tier_probability_multipliers:
        tier_probability_multipliers["contender"] = 1.0
    if "ranked" not in tier_probability_multipliers:
        tier_probability_multipliers["ranked"] = 1.0

    return {
        "include_focus_org_always": bool(raw.get("include_focus_org_always", True)),
        "cross_body_top_window_prob": _clamp_probability(
            raw.get("cross_body_top_window_prob", 0.78),
            0.78,
        ),
        "cross_body_elite_prob": _clamp_probability(
            raw.get("cross_body_elite_prob", 0.56),
            0.56,
        ),
        "cross_body_rank_gap_prob": _clamp_probability(
            raw.get("cross_body_rank_gap_prob", 0.35),
            0.35,
        ),
        "cross_body_single_top10_prob": _clamp_probability(
            raw.get("cross_body_single_top10_prob", 0.3),
            0.3,
        ),
        "cross_body_rank_window": max(1, rank_window),
        "cross_body_elite_cutoff": max(1, elite_cutoff),
        "cross_body_rank_gap_max": max(1, rank_gap_max),
        "opponent_cross_rank_presence_prob": _clamp_probability(
            raw.get("opponent_cross_rank_presence_prob", 0.68),
            0.68,
        ),
        "opponent_unranked_pool_rank_chance": _clamp_probability(
            raw.get("opponent_unranked_pool_rank_chance", 0.2),
            0.2,
        ),
        "opponent_cross_rank_jitter": max(1, jitter),
        "tier_probability_multipliers": tier_probability_multipliers,
    }


def _scaled_probability(
    policy: dict[str, float | int | bool | dict[str, float]],
    *,
    key: str,
    tier_name: str,
) -> float:
    base = float(policy[key])
    tier_map_raw = policy.get("tier_probability_multipliers", {})
    tier_map: dict[str, float] = {}
    if isinstance(tier_map_raw, dict):
        for name, multiplier in tier_map_raw.items():
            try:
                tier_map[str(name).lower()] = float(multiplier)
            except (TypeError, ValueError):
                continue
    tier_multiplier = tier_map.get(tier_name.strip().lower(), 1.0)
    return max(0.0, min(0.97, base * tier_multiplier))


def _ranking_slots(name: str) -> int:
    config = _organization_config(name)
    return max(1, int(config.get("ranking_slots", 40)))


def _weight_classes() -> list[WeightClass]:
    return list_weight_classes()


def _weight_class_names() -> list[str]:
    return [item.name for item in _weight_classes()]


def _weight_class_by_name(name: str) -> WeightClass:
    for weight_class in _weight_classes():
        if weight_class.name == name:
            return weight_class
    raise ValueError(f"Unknown division: {name}")


def _total_pro_fights(state: CareerState) -> int:
    record = state.pro_career.record
    return record.wins + record.losses + record.draws


def _tier_by_fights(fight_count: int) -> dict:
    rules = load_rule_set("pro_career")
    for tier in rules["tiers"]:
        if int(tier["min_fights"]) <= fight_count <= int(tier["max_fights"]):
            return tier
    return rules["tiers"][-1]


def pro_tier(state: CareerState) -> dict:
    return _tier_by_fights(_total_pro_fights(state))


def _seeded_name(state: CareerState, label: str) -> str:
    randomizer = random.Random(f"{state.boxer.profile.name}:{label}")
    return f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}"


def ensure_lineal_titles(state: CareerState) -> None:
    if not state.pro_career.is_active:
        return

    champions = state.pro_career.lineal_champions
    defenses = state.pro_career.lineal_defenses

    for division in _weight_class_names():
        if division not in champions:
            champions[division] = _seeded_name(state, f"lineal:{division}")
        if division not in defenses:
            defenses[division] = 0


def ensure_organization_titles(state: CareerState) -> None:
    if not state.pro_career.is_active:
        return

    canonical = _organization_names()
    champions = state.pro_career.organization_champions
    defenses = state.pro_career.organization_defenses

    if not isinstance(champions, dict):
        state.pro_career.organization_champions = {}
        champions = state.pro_career.organization_champions
    if not isinstance(defenses, dict):
        state.pro_career.organization_defenses = {}
        defenses = state.pro_career.organization_defenses

    for org_name in canonical:
        if org_name not in champions or not isinstance(champions[org_name], dict):
            champions[org_name] = {}
        if org_name not in defenses or not isinstance(defenses[org_name], dict):
            defenses[org_name] = {}

        for division in _weight_class_names():
            if division not in champions[org_name]:
                champions[org_name][division] = _seeded_name(
                    state,
                    f"{org_name}:champ:{division}",
                )
            if division not in defenses[org_name]:
                defenses[org_name][division] = 0


def organization_division_champion(
    state: CareerState,
    organization: str,
    division: str | None = None,
) -> str | None:
    if not state.pro_career.is_active:
        return None
    ensure_organization_titles(state)
    org_name = organization.strip().upper()
    target_division = (division or state.boxer.division).strip().lower()
    return state.pro_career.organization_champions.get(org_name, {}).get(target_division)


def player_lineal_division(state: CareerState) -> str | None:
    if not state.pro_career.is_active:
        return None
    ensure_lineal_titles(state)
    boxer_name = state.boxer.profile.name
    for division, champion in state.pro_career.lineal_champions.items():
        if champion == boxer_name:
            return division
    return None


def current_division_lineal_champion(state: CareerState) -> str | None:
    if not state.pro_career.is_active:
        return None
    ensure_lineal_titles(state)
    return state.pro_career.lineal_champions.get(state.boxer.division)


def ensure_rankings(state: CareerState) -> None:
    canonical = _organization_names()
    if state.pro_career.organization_focus not in canonical:
        state.pro_career.organization_focus = canonical[0]

    if not state.pro_career.rankings:
        state.pro_career.rankings = {name: None for name in canonical}
    else:
        for name in canonical:
            if name not in state.pro_career.rankings:
                state.pro_career.rankings[name] = None

    if state.pro_career.is_active:
        ensure_lineal_titles(state)
        ensure_organization_titles(state)
        if not state.pro_career.divisions_fought:
            state.pro_career.divisions_fought = [state.boxer.division]
        elif state.boxer.division not in state.pro_career.divisions_fought:
            state.pro_career.divisions_fought.append(state.boxer.division)


def _unique_ranked_name(randomizer: random.Random, used_names: set[str]) -> str:
    for _ in range(32):
        candidate = f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate

    idx = len(used_names) + 1
    fallback = f"Contender {idx}"
    used_names.add(fallback)
    return fallback


def _build_rankings_entries(state: CareerState, organization_name: str) -> list[RankingEntry]:
    ensure_rankings(state)
    ranking_slots = _ranking_slots(organization_name)
    player_rank = state.pro_career.rankings.get(organization_name)
    player_record = state.pro_career.record
    player_rating = boxer_overall_rating(
        state.boxer,
        stage="pro",
        pro_record=state.pro_career.record,
    )

    seed = (
        f"{state.boxer.profile.name}:{organization_name}:{state.boxer.division}:"
        f"{state.year}:{state.month}:{_total_pro_fights(state)}"
    )
    randomizer = random.Random(seed)
    used_names = {state.boxer.profile.name}

    lineal_champion = state.pro_career.lineal_champions.get(state.boxer.division)

    entries: list[RankingEntry] = []
    for rank in range(1, ranking_slots + 1):
        if player_rank is not None and rank == player_rank:
            entries.append(
                RankingEntry(
                    rank=rank,
                    name=state.boxer.profile.name,
                    rating=player_rating,
                    wins=player_record.wins,
                    losses=player_record.losses,
                    draws=player_record.draws,
                    division=state.boxer.division,
                    age=state.boxer.profile.age,
                    stance=state.boxer.profile.stance,
                    p4p_score=0.0,
                    is_lineal_champion=lineal_champion == state.boxer.profile.name,
                    is_player=True,
                )
            )
            continue

        if rank == 1 and lineal_champion and lineal_champion != state.boxer.profile.name:
            name = lineal_champion
            used_names.add(name)
            rating = max(89, min(98, int(round(95 + randomizer.gauss(0, 1.2)))))
            wins = max(20, 34 + randomizer.randint(-2, 7))
            losses = max(0, randomizer.randint(0, 4))
            draws = randomizer.randint(0, 3)
        else:
            name = _unique_ranked_name(randomizer, used_names)
            rating = max(55, min(98, int(round(96 - ((rank - 1) * 0.95) + randomizer.gauss(0, 1.2)))))
            wins = max(8, 30 - rank + randomizer.randint(0, 16))
            losses = max(0, (rank // 8) + randomizer.randint(0, 5))
            draws = randomizer.randint(0, 3)

        entries.append(
            RankingEntry(
                rank=rank,
                name=name,
                rating=rating,
                wins=wins,
                losses=losses,
                draws=draws,
                division=state.boxer.division,
                age=randomizer.randint(20, 37),
                stance=randomizer.choice(STANCE_CHOICES),
                p4p_score=0.0,
                is_lineal_champion=(lineal_champion == name),
                is_player=False,
            )
        )

    return entries


def rankings_snapshot(
    state: CareerState,
    organization: str,
    *,
    top_n: int = 20,
) -> list[RankingEntry]:
    if not state.pro_career.is_active:
        raise ValueError("Rankings are available after turning pro.")
    if top_n < 1:
        raise ValueError("top_n must be >= 1.")

    ensure_rankings(state)
    organization_name = organization.strip().upper()
    if organization_name not in _organization_names():
        raise ValueError(f"Unknown organization: {organization_name}")

    ranking_slots = _ranking_slots(organization_name)
    visible_count = min(top_n, ranking_slots)
    player_rank = state.pro_career.rankings.get(organization_name)

    entries = _build_rankings_entries(state, organization_name)
    visible_entries = entries[:visible_count]
    if player_rank is not None and player_rank > visible_count:
        visible_entries.append(entries[player_rank - 1])
    elif player_rank is None:
        player_record = state.pro_career.record
        player_rating = boxer_overall_rating(
            state.boxer,
            stage="pro",
            pro_record=state.pro_career.record,
        )
        visible_entries.append(
            RankingEntry(
                rank=0,
                name=state.boxer.profile.name,
                rating=player_rating,
                wins=player_record.wins,
                losses=player_record.losses,
                draws=player_record.draws,
                division=state.boxer.division,
                age=state.boxer.profile.age,
                stance=state.boxer.profile.stance,
                p4p_score=0.0,
                is_lineal_champion=(current_division_lineal_champion(state) == state.boxer.profile.name),
                is_player=True,
            )
        )
    return visible_entries


def _best_current_rank(state: CareerState) -> int | None:
    ranks = [rank for rank in state.pro_career.rankings.values() if rank is not None]
    if not ranks:
        return None
    return min(ranks)


def _player_p4p_score(state: CareerState) -> float:
    record = state.pro_career.record
    total_fights = max(1, record.wins + record.losses + record.draws)
    rating = boxer_overall_rating(state.boxer, stage="pro", pro_record=state.pro_career.record)
    best_rank = _best_current_rank(state)
    quality_score = 0.0 if best_rank is None else max(0.0, (41 - best_rank) * 0.9)

    ko_ratio = 0.0 if record.wins <= 0 else (record.kos / record.wins)
    resume_score = (record.wins * 1.6) - (record.losses * 2.4) + (record.draws * 0.5) + (ko_ratio * 8.0)

    lineal_division = player_lineal_division(state)
    lineal_bonus = 0.0
    if lineal_division is not None:
        lineal_bonus = 14.0 + (state.pro_career.lineal_defenses.get(lineal_division, 0) * 1.5)

    divisions_count = len(state.pro_career.divisions_fought) if state.pro_career.divisions_fought else 1
    multi_division_bonus = (divisions_count * 2.5) + (state.pro_career.division_changes * 0.8)

    fights_per_year = (_total_pro_fights(state) * 12.0) / max(1, state.career_months)
    activity_score = max(0.0, min(12.0, fights_per_year * 2.8))

    return round((rating * 1.85) + resume_score + quality_score + lineal_bonus + multi_division_bonus + activity_score, 2)


def _npc_p4p_score(
    *,
    rating: int,
    wins: int,
    losses: int,
    draws: int,
    is_lineal: bool,
    rank_hint: int,
    randomizer: random.Random,
) -> float:
    quality_score = max(0.0, (41 - min(40, rank_hint)) * 0.55)
    resume_score = (wins * 1.1) - (losses * 1.9) + (draws * 0.35)
    lineal_bonus = 10.0 if is_lineal else 0.0
    activity_score = randomizer.uniform(3.0, 8.0)
    score = (rating * 1.5) + resume_score + quality_score + lineal_bonus + activity_score
    return round(score, 2)


def _p4p_pool_entries(state: CareerState) -> list[PoundForPoundEntry]:
    ensure_rankings(state)
    seed = (
        f"p4p:{state.boxer.profile.name}:{state.year}:{state.month}:"
        f"{_total_pro_fights(state)}:{state.boxer.division}:{state.pro_career.division_changes}"
    )
    randomizer = random.Random(seed)

    used_names = {state.boxer.profile.name}
    lineal_champions = {
        division: champion
        for division, champion in state.pro_career.lineal_champions.items()
        if champion
    }
    used_names.update(champion for champion in lineal_champions.values() if champion)

    entries: list[PoundForPoundEntry] = []

    for division, champion in lineal_champions.items():
        if champion == state.boxer.profile.name:
            continue
        champ_seed = random.Random(f"p4p-lineal:{state.boxer.profile.name}:{division}:{champion}")
        rating = champ_seed.randint(84, 95)
        wins = champ_seed.randint(16, 34)
        losses = champ_seed.randint(0, 5)
        draws = champ_seed.randint(0, 3)
        score = _npc_p4p_score(
            rating=rating,
            wins=wins,
            losses=losses,
            draws=draws,
            is_lineal=True,
            rank_hint=1,
            randomizer=champ_seed,
        )
        entries.append(
            PoundForPoundEntry(
                rank=0,
                name=champion,
                score=score,
                rating=rating,
                division=division,
                wins=wins,
                losses=losses,
                draws=draws,
                is_lineal_champion=True,
                is_player=False,
            )
        )

    divisions = _weight_class_names()
    while len(entries) < 65:
        division = randomizer.choice(divisions)
        name = _unique_ranked_name(randomizer, used_names)
        rating = randomizer.randint(76, 98)
        wins = randomizer.randint(12, 44)
        losses = randomizer.randint(0, 8)
        draws = randomizer.randint(0, 4)
        rank_hint = randomizer.randint(1, 30)
        score = _npc_p4p_score(
            rating=rating,
            wins=wins,
            losses=losses,
            draws=draws,
            is_lineal=(lineal_champions.get(division) == name),
            rank_hint=rank_hint,
            randomizer=randomizer,
        )
        entries.append(
            PoundForPoundEntry(
                rank=0,
                name=name,
                score=score,
                rating=rating,
                division=division,
                wins=wins,
                losses=losses,
                draws=draws,
                is_lineal_champion=(lineal_champions.get(division) == name),
                is_player=False,
            )
        )

    return entries


def pound_for_pound_snapshot(state: CareerState, *, top_n: int = 20) -> list[PoundForPoundEntry]:
    if not state.pro_career.is_active:
        raise ValueError("Pound-for-pound rankings are available after turning pro.")
    if top_n < 1:
        raise ValueError("top_n must be >= 1.")

    ensure_rankings(state)
    pool = _p4p_pool_entries(state)
    player_record = state.pro_career.record
    player_entry = PoundForPoundEntry(
        rank=0,
        name=state.boxer.profile.name,
        score=_player_p4p_score(state),
        rating=boxer_overall_rating(state.boxer, stage="pro", pro_record=state.pro_career.record),
        division=state.boxer.division,
        wins=player_record.wins,
        losses=player_record.losses,
        draws=player_record.draws,
        is_lineal_champion=(player_lineal_division(state) is not None),
        is_player=True,
    )
    pool.append(player_entry)

    sorted_pool = sorted(
        pool,
        key=lambda item: (item.score, item.rating, item.wins - item.losses),
        reverse=True,
    )

    ranked: list[PoundForPoundEntry] = []
    for idx, item in enumerate(sorted_pool, start=1):
        ranked.append(
            PoundForPoundEntry(
                rank=idx,
                name=item.name,
                score=item.score,
                rating=item.rating,
                division=item.division,
                wins=item.wins,
                losses=item.losses,
                draws=item.draws,
                is_lineal_champion=item.is_lineal_champion,
                is_player=item.is_player,
            )
        )

    visible = ranked[:top_n]
    player_ranked = next((item for item in ranked if item.is_player), None)
    if player_ranked is not None and player_ranked.rank > top_n:
        visible.append(player_ranked)
    return visible


def player_pound_for_pound_position(state: CareerState) -> tuple[int | None, float]:
    if not state.pro_career.is_active:
        return None, 0.0

    table = pound_for_pound_snapshot(state, top_n=120)
    for row in table:
        if row.is_player:
            return row.rank, row.score
    return None, _player_p4p_score(state)


def _seed_rank_from_p4p(state: CareerState, randomizer: random.Random) -> int | None:
    if _total_pro_fights(state) < 2:
        return None

    p4p_rank, _ = player_pound_for_pound_position(state)
    if p4p_rank is None:
        return None

    if p4p_rank <= 3:
        return randomizer.randint(4, 6)
    if p4p_rank <= 8:
        return randomizer.randint(7, 10)
    if p4p_rank <= 15:
        return randomizer.randint(11, 15)
    if p4p_rank <= 25:
        return randomizer.randint(16, 22)
    if p4p_rank <= 40:
        return randomizer.randint(23, 30)
    if p4p_rank <= 60:
        return randomizer.randint(31, 36)
    return None


def available_division_moves(state: CareerState) -> list[str]:
    if not state.pro_career.is_active:
        return []

    divisions = _weight_classes()
    names = [item.name for item in divisions]
    current = state.boxer.division
    if current not in names:
        return []

    idx = names.index(current)
    options: list[str] = []
    if idx > 0:
        options.append(names[idx - 1])
    if idx < len(names) - 1:
        options.append(names[idx + 1])
    return options


def _blended_stats_for_division(state: CareerState, target_weight_class: WeightClass) -> dict[str, int]:
    boxer = state.boxer
    base_stats = build_stats(
        height_inches=boxer.profile.height_inches,
        weight_lbs=target_weight_class.max_lbs,
        weight_class=target_weight_class,
    ).to_dict()

    current_stats = boxer.stats.to_dict()
    merged: dict[str, int] = {}
    for key, value in current_stats.items():
        merged[key] = _clamp_stat(int(round((value * 0.72) + (base_stats[key] * 0.28))))
    return merged


def change_division(
    state: CareerState,
    target_division: str,
    rng: random.Random | None = None,
) -> dict[str, int | str | None]:
    if not state.pro_career.is_active:
        raise ValueError("Turn pro before changing divisions.")

    ensure_rankings(state)
    randomizer = rng or random.Random()

    target = target_division.strip().lower()
    if not target:
        raise ValueError("Target division is required.")

    current_division = state.boxer.division
    if target == current_division:
        raise ValueError("Already in that division.")

    classes = _weight_classes()
    names = [item.name for item in classes]
    if target not in names:
        raise ValueError(f"Unknown division: {target}")

    current_idx = names.index(current_division)
    target_idx = names.index(target)
    step_distance = abs(target_idx - current_idx)
    if step_distance != 1:
        raise ValueError("You can move only one division at a time.")

    current_weight = state.boxer.profile.weight_lbs
    target_weight_class = _weight_class_by_name(target)
    new_weight = target_weight_class.max_lbs
    moving_down = target_idx < current_idx
    cut_lbs = max(0, current_weight - new_weight)

    had_lineal = player_lineal_division(state) == current_division
    if had_lineal:
        state.pro_career.lineal_champions[current_division] = None
        state.pro_career.lineal_defenses[current_division] = 0

    vacated_org_titles = 0
    ensure_organization_titles(state)
    boxer_name = state.boxer.profile.name
    for org_name in _organization_names():
        champion = organization_division_champion(state, org_name, current_division)
        if champion == boxer_name:
            state.pro_career.organization_champions[org_name][current_division] = None
            state.pro_career.organization_defenses[org_name][current_division] = 0
            vacated_org_titles += 1

    seed_rank = _seed_rank_from_p4p(state, randomizer)

    for org_name in _organization_names():
        if seed_rank is None:
            state.pro_career.rankings[org_name] = None
            continue
        jitter = randomizer.randint(-1, 1)
        state.pro_career.rankings[org_name] = max(1, min(_ranking_slots(org_name), seed_rank + jitter))

    merged_stats = _blended_stats_for_division(state, target_weight_class)
    if moving_down:
        merged_stats["stamina"] = _clamp_stat(merged_stats["stamina"] - 2)
        merged_stats["chin"] = _clamp_stat(merged_stats["chin"] - 2)
        merged_stats["power"] = _clamp_stat(merged_stats["power"] - 1)
        merged_stats["speed"] = _clamp_stat(merged_stats["speed"] + 1)

        fatigue_gain = 5 + max(1, cut_lbs // 2)
        injury_gain = 14 + (cut_lbs * 2)
    else:
        merged_stats["power"] = _clamp_stat(merged_stats["power"] + 1)
        merged_stats["chin"] = _clamp_stat(merged_stats["chin"] + 1)
        merged_stats["speed"] = _clamp_stat(merged_stats["speed"] - 1)
        merged_stats["footwork"] = _clamp_stat(merged_stats["footwork"] - 1)

        gain_lbs = max(0, new_weight - current_weight)
        fatigue_gain = 2 + max(0, gain_lbs // 8)
        injury_gain = 4 + max(0, gain_lbs // 6)

    state.boxer.stats = Stats.from_dict(merged_stats)
    state.boxer.profile.weight_lbs = new_weight
    state.boxer.division = target
    state.boxer.fatigue = min(12, state.boxer.fatigue + fatigue_gain)
    state.boxer.injury_risk = min(100, state.boxer.injury_risk + injury_gain)

    state.pro_career.division_changes += 1
    if target not in state.pro_career.divisions_fought:
        state.pro_career.divisions_fought.append(target)

    ensure_lineal_titles(state)

    return {
        "from_division": current_division,
        "to_division": target,
        "seed_rank": seed_rank,
        "moving_down": int(moving_down),
        "cut_lbs": cut_lbs,
        "fatigue_gain": fatigue_gain,
        "injury_risk_gain": injury_gain,
        "vacated_lineal": int(had_lineal),
        "vacated_org_titles": vacated_org_titles,
    }


def turn_pro(state: CareerState, rng: random.Random | None = None) -> dict[str, str | int]:
    if state.pro_career.is_active:
        raise ValueError("Boxer is already pro.")
    if state.is_retired:
        raise ValueError("Retired boxer cannot turn pro.")
    if not pro_ready(state):
        raise ValueError("Pro readiness not reached yet.")

    randomizer = rng or random.Random()
    rules = load_rule_set("pro_career")

    promoter = randomizer.choice(list(rules["promoters"]))
    organization_focus = randomizer.choice(_organization_names())
    bonus_cfg = rules["turn_pro"]
    signing_bonus = randomizer.randint(
        int(bonus_cfg["signing_bonus_min"]),
        int(bonus_cfg["signing_bonus_max"]),
    )

    state.pro_career = ProCareer(
        is_active=True,
        promoter=promoter,
        organization_focus=organization_focus,
        rankings={name: None for name in _organization_names()},
        organization_champions={},
        organization_defenses={},
        record=CareerRecord(),
        purse_balance=float(signing_bonus),
        total_earnings=float(signing_bonus),
        lineal_champions={},
        lineal_defenses={},
        division_changes=0,
        divisions_fought=[state.boxer.division],
        last_world_news=[],
        last_player_fight_month=state.career_months,
    )
    ensure_rankings(state)
    state.boxer.popularity += 3
    return {
        "promoter": promoter,
        "organization_focus": organization_focus,
        "signing_bonus": signing_bonus,
    }


def _pick_ranked_opponent_entry(state: CareerState, randomizer: random.Random) -> RankingEntry | None:
    focus_org = state.pro_career.organization_focus
    player_rank = state.pro_career.rankings.get(focus_org)
    if player_rank is None:
        return None

    ranking_slots = _ranking_slots(focus_org)
    full_rankings = _build_rankings_entries(state, focus_org)
    lineal_champion = current_division_lineal_champion(state)
    org_champion = organization_division_champion(state, focus_org, state.boxer.division)
    boxer_name = state.boxer.profile.name

    selected_rank: int | None = None

    if (
        player_rank <= 5
        and org_champion
        and org_champion != boxer_name
        and randomizer.random() < 0.38
    ):
        return RankingEntry(
            rank=1,
            name=org_champion,
            rating=max(90, randomizer.randint(91, 97)),
            wins=randomizer.randint(18, 34),
            losses=randomizer.randint(0, 4),
            draws=randomizer.randint(0, 3),
            division=state.boxer.division,
            age=randomizer.randint(24, 36),
            stance=randomizer.choice(STANCE_CHOICES),
            p4p_score=0.0,
            is_lineal_champion=(lineal_champion == org_champion),
            is_player=False,
        )

    if player_rank <= 3:
        if lineal_champion and lineal_champion != boxer_name and randomizer.random() < 0.55:
            selected_rank = 1
        elif lineal_champion is None and randomizer.random() < 0.65:
            if player_rank == 1:
                selected_rank = randomizer.choice([2, 3])
            elif player_rank == 2:
                selected_rank = 1
            else:
                selected_rank = 1

    if selected_rank is None:
        spread = 6 if player_rank > 10 else 4
        low = max(1, player_rank - spread)
        high = min(ranking_slots, player_rank + spread)
        selected_rank = randomizer.randint(low, high)

    chosen = next(
        (item for item in full_rankings if item.rank == selected_rank and not item.is_player),
        None,
    )
    if chosen is not None:
        return chosen

    fallback_rank = selected_rank + 1 if selected_rank < ranking_slots else selected_rank - 1
    return next(
        (item for item in full_rankings if item.rank == fallback_rank and not item.is_player),
        None,
    )


def _build_opponent_org_ranks(
    *,
    state: CareerState,
    focus_org: str,
    focus_rank: int | None,
    randomizer: random.Random,
) -> dict[str, int | None]:
    policy = _sanctioning_policy()
    tier_name = str(pro_tier(state).get("name", "contender"))
    unranked_pool_chance = _scaled_probability(
        policy,
        key="opponent_unranked_pool_rank_chance",
        tier_name=tier_name,
    )
    cross_rank_presence_prob = _scaled_probability(
        policy,
        key="opponent_cross_rank_presence_prob",
        tier_name=tier_name,
    )
    jitter_max = int(policy["opponent_cross_rank_jitter"])

    ranks: dict[str, int | None] = {}
    for org_name in _organization_names():
        slots = _ranking_slots(org_name)
        if org_name == focus_org:
            ranks[org_name] = None if focus_rank is None else max(1, min(slots, int(focus_rank)))
            continue

        if focus_rank is None:
            if randomizer.random() < unranked_pool_chance:
                ranks[org_name] = randomizer.randint(max(8, slots - 16), slots)
            else:
                ranks[org_name] = None
            continue

        if randomizer.random() < cross_rank_presence_prob:
            jitter = randomizer.randint(-jitter_max, jitter_max)
            ranks[org_name] = max(1, min(slots, int(focus_rank) + jitter))
        else:
            ranks[org_name] = None
    return ranks


def determine_sanctioning_bodies(
    state: CareerState,
    opponent: Opponent,
    rng: random.Random | None = None,
) -> list[str]:
    if not state.pro_career.is_active:
        return []
    ensure_rankings(state)

    randomizer = rng or random.Random()
    boxer_name = state.boxer.profile.name
    focus_org = state.pro_career.organization_focus
    division = state.boxer.division
    policy = _sanctioning_policy()
    tier_name = str(pro_tier(state).get("name", "contender"))
    top_window = int(policy["cross_body_rank_window"])
    elite_cutoff = int(policy["cross_body_elite_cutoff"])
    rank_gap_max = int(policy["cross_body_rank_gap_max"])

    sanctioned: list[str] = []
    for org_name in _organization_names():
        player_rank = state.pro_career.rankings.get(org_name)
        opponent_rank = opponent.organization_ranks.get(org_name)
        champion = organization_division_champion(state, org_name, division)
        is_title_fight = champion in {boxer_name, opponent.name}

        if is_title_fight:
            sanctioned.append(org_name)
            continue

        if player_rank is not None and opponent_rank is not None:
            if (
                player_rank <= top_window
                and opponent_rank <= top_window
                and randomizer.random()
                < _scaled_probability(
                    policy,
                    key="cross_body_top_window_prob",
                    tier_name=tier_name,
                )
            ):
                sanctioned.append(org_name)
            elif (
                (player_rank <= elite_cutoff or opponent_rank <= elite_cutoff)
                and randomizer.random()
                < _scaled_probability(
                    policy,
                    key="cross_body_elite_prob",
                    tier_name=tier_name,
                )
            ):
                sanctioned.append(org_name)
            elif (
                abs(player_rank - opponent_rank) <= rank_gap_max
                and randomizer.random()
                < _scaled_probability(
                    policy,
                    key="cross_body_rank_gap_prob",
                    tier_name=tier_name,
                )
            ):
                sanctioned.append(org_name)
            continue

        contender_rank = min(
            item
            for item in [
                player_rank if player_rank is not None else 99,
                opponent_rank if opponent_rank is not None else 99,
            ]
        )
        if (
            contender_rank <= 10
            and randomizer.random()
            < _scaled_probability(
                policy,
                key="cross_body_single_top10_prob",
                tier_name=tier_name,
            )
        ):
            sanctioned.append(org_name)

    if bool(policy["include_focus_org_always"]) and focus_org not in sanctioned:
        sanctioned.append(focus_org)

    if not sanctioned:
        sanctioned = [focus_org]

    canonical_order = _organization_names()
    return [org_name for org_name in canonical_order if org_name in sanctioned]


def generate_pro_opponent(state: CareerState, rng: random.Random | None = None) -> Opponent:
    if not state.pro_career.is_active:
        raise ValueError("Turn pro before scheduling pro fights.")
    ensure_rankings(state)

    randomizer = rng or random.Random()
    tier = pro_tier(state)
    boxer = state.boxer
    focus_org = state.pro_career.organization_focus
    weight_class = classify_weight(boxer.profile.weight_lbs)

    ranked_entry = _pick_ranked_opponent_entry(state, randomizer)

    rating_floor = int(tier["opponent_rating_min"])
    rating_ceiling = int(tier["opponent_rating_max"])
    if ranked_entry is not None:
        rating = max(rating_floor, min(98, ranked_entry.rating + randomizer.randint(-1, 1)))
        name = ranked_entry.name
        focus_rank = ranked_entry.rank
        wins = ranked_entry.wins
        losses = ranked_entry.losses
        draws = ranked_entry.draws
        is_lineal_champion = ranked_entry.is_lineal_champion
    else:
        rating = randomizer.randint(rating_floor, rating_ceiling)
        name = f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}"
        focus_rank = None
        wins = max(2, rating // 6 + randomizer.randint(0, 6))
        losses = max(0, wins // 4 + randomizer.randint(0, 4))
        draws = randomizer.randint(0, 3)
        is_lineal_champion = False

    if is_lineal_champion:
        rating = max(rating, randomizer.randint(89, 97))

    height_inches = max(
        58,
        min(84, randomizer.randint(weight_class.avg_height_in - 4, weight_class.avg_height_in + 4)),
    )
    height_ft = height_inches // 12
    height_in = height_inches % 12

    min_weight = max(weight_class.min_lbs, boxer.profile.weight_lbs - 5)
    max_weight = min(weight_class.max_lbs, boxer.profile.weight_lbs + 5)
    if min_weight > max_weight:
        min_weight, max_weight = weight_class.min_lbs, weight_class.max_lbs

    weight_lbs = randomizer.randint(min_weight, max_weight)
    base_stats = build_stats(
        height_inches=height_inches,
        weight_lbs=weight_lbs,
        weight_class=weight_class,
    )
    shift = int(round((rating - _mean_stat(base_stats)) * 0.6))
    adjusted = {k: _clamp_stat(v + shift) for k, v in base_stats.to_dict().items()}
    organization_ranks = _build_opponent_org_ranks(
        state=state,
        focus_org=focus_org,
        focus_rank=focus_rank,
        randomizer=randomizer,
    )

    current_division = state.boxer.division
    if not is_lineal_champion:
        for org_name in _organization_names():
            champion = organization_division_champion(state, org_name, current_division)
            if champion == name:
                is_lineal_champion = True
                if organization_ranks.get(org_name) is None:
                    organization_ranks[org_name] = 1
                break

    return Opponent(
        name=name,
        age=randomizer.randint(20, 38),
        stance=randomizer.choice(STANCE_CHOICES),
        height_ft=height_ft,
        height_in=height_in,
        weight_lbs=weight_lbs,
        division=boxer.division,
        stats=Stats.from_dict(adjusted),
        rating=rating,
        record=CareerRecord(
            wins=wins,
            losses=losses,
            draws=draws,
            kos=max(1, wins // 2),
        ),
        ranking_position=organization_ranks.get(focus_org),
        organization_ranks=organization_ranks,
        is_lineal_champion=is_lineal_champion,
    )


def offer_purse(
    state: CareerState,
    opponent: Opponent,
    rng: random.Random | None = None,
) -> dict[str, float | list[str]]:
    if not state.pro_career.is_active:
        raise ValueError("Turn pro before requesting a purse offer.")
    ensure_rankings(state)

    randomizer = rng or random.Random()
    rules = load_rule_set("pro_career")
    tier = pro_tier(state)
    economy = rules["economy"]
    purse_cfg = tier["purse"]

    base = randomizer.randint(int(purse_cfg["min"]), int(purse_cfg["max"]))
    popularity_bonus = state.boxer.popularity * float(economy["popularity_bonus_per_point"])
    rating_bonus = opponent.rating * float(economy["opponent_rating_bonus"])

    focus_org = state.pro_career.organization_focus
    current_rank = state.pro_career.rankings.get(focus_org)
    rank_bonus = 0.0
    if current_rank is not None:
        rank_bonus = max(0.0, (41 - current_rank) * float(economy["ranking_bonus_per_step"]))

    lineal_bonus = 3500.0 if opponent.is_lineal_champion else 0.0

    gross = float(base + popularity_bonus + rating_bonus + rank_bonus + lineal_bonus)

    manager_cut = gross * float(economy["manager_cut_pct"])
    trainer_cut = gross * float(economy["trainer_cut_pct"])
    camp_cost = gross * float(economy["camp_cost_pct"])
    commission_cut = gross * float(economy["commission_pct"])
    sanctioning_bodies = determine_sanctioning_bodies(state, opponent, rng=randomizer)
    sanction_fee = 0.0
    boxer_name = state.boxer.profile.name
    division = state.boxer.division
    for org_name in sanctioning_bodies:
        org_cfg = _organization_config(org_name)
        threshold = int(org_cfg["sanction_fee_rank_threshold"])
        player_rank = state.pro_career.rankings.get(org_name)
        opponent_rank = opponent.organization_ranks.get(org_name)
        champion = organization_division_champion(state, org_name, division)
        is_title_fight = champion in {boxer_name, opponent.name}
        has_ranked_interest = (
            (player_rank is not None and player_rank <= threshold)
            or (opponent_rank is not None and opponent_rank <= threshold)
        )
        if is_title_fight or has_ranked_interest:
            sanction_fee += gross * float(org_cfg["sanction_fee_pct"])

    net = gross - manager_cut - trainer_cut - camp_cost - commission_cut - sanction_fee
    total_expenses = manager_cut + trainer_cut + camp_cost + commission_cut + sanction_fee

    return {
        "gross": round(gross, 2),
        "manager_cut": round(manager_cut, 2),
        "trainer_cut": round(trainer_cut, 2),
        "camp_cost": round(camp_cost, 2),
        "commission_cut": round(commission_cut, 2),
        "sanction_fee": round(sanction_fee, 2),
        "total_expenses": round(total_expenses, 2),
        "net": round(max(0.0, net), 2),
        "sanctioning_bodies": sanctioning_bodies,
    }


def format_purse_breakdown(purse_breakdown: dict[str, float | list[str]]) -> str:
    sanctioning_bodies = purse_breakdown.get("sanctioning_bodies", [])
    sanctioned_label = ""
    if isinstance(sanctioning_bodies, list) and sanctioning_bodies:
        bodies = ", ".join(str(item) for item in sanctioning_bodies)
        sanctioned_label = f" | Bodies {bodies}"
    return (
        f"Gross ${purse_breakdown['gross']:,.2f} | "
        f"Manager ${purse_breakdown['manager_cut']:,.2f} | "
        f"Trainer ${purse_breakdown['trainer_cut']:,.2f} | "
        f"Camp ${purse_breakdown['camp_cost']:,.2f} | "
        f"Commission ${purse_breakdown['commission_cut']:,.2f} | "
        f"Sanction ${purse_breakdown['sanction_fee']:,.2f} | "
        f"Net ${purse_breakdown['net']:,.2f}"
        f"{sanctioned_label}"
    )


def _update_organization_ranking(
    state: CareerState,
    result: FightResult,
    organization_name: str,
) -> int | None:
    ensure_rankings(state)
    tier = pro_tier(state)
    ranking_cfg = tier["ranking"]
    boxer_name = state.boxer.profile.name
    org_name = organization_name.strip().upper()
    if org_name not in _organization_names():
        raise ValueError(f"Unknown organization: {org_name}")
    ranking_slots = _ranking_slots(org_name)

    current_rank = state.pro_career.rankings.get(org_name)
    new_rank = current_rank

    if result.winner == boxer_name:
        if current_rank is None:
            new_rank = int(ranking_cfg["entry_on_win"])
        else:
            new_rank = max(1, current_rank - int(ranking_cfg["win_step"]))
    elif result.winner == "Draw":
        if current_rank is not None:
            new_rank = min(ranking_slots, current_rank + int(ranking_cfg["draw_penalty"]))
    else:
        if current_rank is not None:
            new_rank = min(ranking_slots, current_rank + int(ranking_cfg["loss_penalty"]))

    if new_rank is not None:
        new_rank = max(1, min(ranking_slots, int(new_rank)))

    state.pro_career.rankings[org_name] = new_rank
    return new_rank


def _vacancy_fight_is_valid(player_rank: int | None, opponent_rank: int | None) -> bool:
    if player_rank is None or opponent_rank is None:
        return False
    pairing = {int(player_rank), int(opponent_rank)}
    return pairing in ({1, 2}, {1, 3})


def _update_lineal_after_fight(
    state: CareerState,
    opponent: Opponent,
    result: FightResult,
    player_rank_before: int | None,
) -> str:
    ensure_lineal_titles(state)
    division = state.boxer.division
    boxer_name = state.boxer.profile.name

    champion = state.pro_career.lineal_champions.get(division)
    if opponent.is_lineal_champion and champion != opponent.name:
        champion = opponent.name
        state.pro_career.lineal_champions[division] = opponent.name

    opponent_rank = opponent.ranking_position

    if champion is None:
        if not _vacancy_fight_is_valid(player_rank_before, opponent_rank):
            return ""

        if result.winner == boxer_name:
            state.pro_career.lineal_champions[division] = boxer_name
            state.pro_career.lineal_defenses[division] = 0
            return f"Captured vacant lineal title at {division}."

        if result.winner == opponent.name:
            state.pro_career.lineal_champions[division] = opponent.name
            state.pro_career.lineal_defenses[division] = 0
            return f"{opponent.name} won the vacant lineal title at {division}."

        return f"Vacant lineal title at {division} remains vacant after draw."

    if champion == boxer_name:
        if result.winner == boxer_name:
            new_defenses = state.pro_career.lineal_defenses.get(division, 0) + 1
            state.pro_career.lineal_defenses[division] = new_defenses
            return f"Lineal title defense #{new_defenses} at {division}."

        if result.winner == opponent.name:
            state.pro_career.lineal_champions[division] = opponent.name
            state.pro_career.lineal_defenses[division] = 0
            return f"Lost lineal title at {division} to {opponent.name}."

        return f"Retained lineal title at {division} after draw."

    if champion == opponent.name:
        if result.winner == boxer_name:
            state.pro_career.lineal_champions[division] = boxer_name
            state.pro_career.lineal_defenses[division] = 0
            return f"Captured lineal title at {division} from {opponent.name}."

        if result.winner == opponent.name:
            new_defenses = state.pro_career.lineal_defenses.get(division, 0) + 1
            state.pro_career.lineal_defenses[division] = new_defenses
            return f"{opponent.name} retained lineal title at {division}."

        return f"{opponent.name} retained lineal title at {division} after draw."

    return ""


def _normalized_sanctioning_bodies(raw_value: object, focus_org: str) -> list[str]:
    canonical = _organization_names()
    if not isinstance(raw_value, list):
        return [focus_org]
    selected = {str(item).strip().upper() for item in raw_value}
    ordered = [org_name for org_name in canonical if org_name in selected]
    if focus_org not in ordered:
        ordered.append(focus_org)
    return ordered


def _update_organization_titles_after_fight(
    state: CareerState,
    opponent: Opponent,
    result: FightResult,
    sanctioned_bodies: list[str],
) -> list[str]:
    ensure_organization_titles(state)
    boxer_name = state.boxer.profile.name
    division = state.boxer.division
    notes: list[str] = []

    for org_name in sanctioned_bodies:
        champion = organization_division_champion(state, org_name, division)
        if champion not in {boxer_name, opponent.name}:
            continue

        defenses = state.pro_career.organization_defenses[org_name]
        champions = state.pro_career.organization_champions[org_name]

        if champion == boxer_name:
            if result.winner == boxer_name:
                defenses[division] = defenses.get(division, 0) + 1
                state.pro_career.rankings[org_name] = 1
                notes.append(f"{org_name} title defense successful.")
            elif result.winner == opponent.name:
                champions[division] = opponent.name
                defenses[division] = 0
                notes.append(f"Lost {org_name} title to {opponent.name}.")
            else:
                notes.append(f"Retained {org_name} title in a draw.")
            continue

        if champion == opponent.name:
            if result.winner == boxer_name:
                champions[division] = boxer_name
                defenses[division] = 0
                state.pro_career.rankings[org_name] = 1
                notes.append(f"Captured {org_name} title from {opponent.name}.")
            elif result.winner == opponent.name:
                defenses[division] = defenses.get(division, 0) + 1
                notes.append(f"{opponent.name} retained {org_name} title.")
            else:
                notes.append(f"{opponent.name} retained {org_name} title in a draw.")
    return notes


def apply_pro_fight_result(
    state: CareerState,
    opponent: Opponent,
    result: FightResult,
    purse_breakdown: dict[str, float | list[str]],
) -> int | None:
    if not state.pro_career.is_active:
        raise ValueError("Turn pro before applying pro results.")
    ensure_rankings(state)

    record = state.pro_career.record
    boxer_name = state.boxer.profile.name
    tier = pro_tier(state)
    popularity_cfg = tier["popularity"]

    focus_org = state.pro_career.organization_focus
    player_rank_before = state.pro_career.rankings.get(focus_org)
    sanctioned_bodies = _normalized_sanctioning_bodies(
        purse_breakdown.get("sanctioning_bodies"),
        focus_org,
    )

    if result.winner == boxer_name:
        record.wins += 1
        state.boxer.popularity += int(popularity_cfg["win"])
        if result.method in {"KO", "TKO"}:
            record.kos += 1
    elif result.winner == "Draw":
        record.draws += 1
        state.boxer.popularity += int(popularity_cfg["draw"])
    else:
        record.losses += 1
        state.boxer.popularity = max(1, state.boxer.popularity + int(popularity_cfg["loss"]))

    experience_gain = fight_experience_gain(
        stage="pro",
        boxer_name=boxer_name,
        opponent_rating=opponent.rating,
        result=result,
    )
    add_experience_points(state.boxer, experience_gain)

    state.pro_career.purse_balance += float(purse_breakdown["net"])
    state.pro_career.total_earnings += float(purse_breakdown["gross"])
    impact = calculate_post_fight_impact(
        stage="pro",
        boxer_name=boxer_name,
        result=result,
        rounds_scheduled=int(tier["rounds"]),
    )
    fatigue_gain = adjusted_fatigue_gain(state, impact.fatigue_gain)
    injury_gain = adjusted_injury_risk_gain(state, impact.injury_risk_gain)
    state.boxer.fatigue = min(12, state.boxer.fatigue + fatigue_gain)
    state.boxer.injury_risk = min(100, state.boxer.injury_risk + injury_gain)

    rank_updates: dict[str, int | None] = {}
    for org_name in sanctioned_bodies:
        rank_updates[org_name] = _update_organization_ranking(state, result, org_name)
    new_rank = rank_updates.get(focus_org, state.pro_career.rankings.get(focus_org))

    state.pro_career.last_player_fight_month = state.career_months
    lineal_note = _update_lineal_after_fight(state, opponent, result, player_rank_before)
    org_title_notes = _update_organization_titles_after_fight(
        state,
        opponent,
        result,
        sanctioned_bodies,
    )
    sanction_note = f"Sanctioned bodies: {', '.join(sanctioned_bodies)}."
    rank_note_parts = []
    for org_name in sanctioned_bodies:
        rank_value = rank_updates.get(org_name)
        rank_label = f"#{rank_value}" if rank_value is not None else "Unranked"
        rank_note_parts.append(f"{org_name} {rank_label}")
    rank_note = f"Rank updates: {', '.join(rank_note_parts)}."

    notes_parts = [lineal_note, sanction_note, rank_note, *org_title_notes]
    combined_notes = " ".join(part for part in notes_parts if part).strip()

    state.history.append(
        FightHistoryEntry(
            opponent_name=opponent.name,
            opponent_rating=opponent.rating,
            result=result,
            stage="pro",
            purse=float(purse_breakdown["net"]),
            notes=combined_notes,
        )
    )
    return new_rank
