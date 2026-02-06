from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from boxing_game.constants import STARTING_AGE


@dataclass
class Stats:
    power: int
    speed: int
    chin: int
    stamina: int
    defense: int
    ring_iq: int
    footwork: int
    reach_control: int
    inside_fighting: int

    def to_dict(self) -> dict[str, int]:
        return {
            "power": self.power,
            "speed": self.speed,
            "chin": self.chin,
            "stamina": self.stamina,
            "defense": self.defense,
            "ring_iq": self.ring_iq,
            "footwork": self.footwork,
            "reach_control": self.reach_control,
            "inside_fighting": self.inside_fighting,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Stats":
        return cls(
            power=int(payload["power"]),
            speed=int(payload["speed"]),
            chin=int(payload["chin"]),
            stamina=int(payload["stamina"]),
            defense=int(payload["defense"]),
            ring_iq=int(payload["ring_iq"]),
            footwork=int(payload["footwork"]),
            reach_control=int(payload["reach_control"]),
            inside_fighting=int(payload["inside_fighting"]),
        )


@dataclass
class CareerRecord:
    wins: int = 0
    losses: int = 0
    draws: int = 0
    kos: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "kos": self.kos,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CareerRecord":
        return cls(
            wins=int(payload.get("wins", 0)),
            losses=int(payload.get("losses", 0)),
            draws=int(payload.get("draws", 0)),
            kos=int(payload.get("kos", 0)),
        )


@dataclass
class BoxerProfile:
    name: str
    age: int
    stance: str
    height_ft: int
    height_in: int
    weight_lbs: int
    reach_in: int
    nationality: str = "USA"

    @property
    def height_inches(self) -> int:
        return self.height_ft * 12 + self.height_in

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "age": self.age,
            "stance": self.stance,
            "height_ft": self.height_ft,
            "height_in": self.height_in,
            "weight_lbs": self.weight_lbs,
            "reach_in": self.reach_in,
            "nationality": self.nationality,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BoxerProfile":
        return cls(
            name=str(payload["name"]),
            age=int(payload["age"]),
            stance=str(payload["stance"]),
            height_ft=int(payload["height_ft"]),
            height_in=int(payload["height_in"]),
            weight_lbs=int(payload["weight_lbs"]),
            reach_in=int(payload["reach_in"]),
            nationality=str(payload.get("nationality", "USA")),
        )


@dataclass
class AgingProfile:
    peak_age: int
    decline_onset_age: int
    decline_severity: float
    iq_growth_factor: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "peak_age": self.peak_age,
            "decline_onset_age": self.decline_onset_age,
            "decline_severity": self.decline_severity,
            "iq_growth_factor": self.iq_growth_factor,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgingProfile":
        peak_age = int(payload.get("peak_age", 28))
        decline_onset_age = int(payload.get("decline_onset_age", peak_age + 2))
        decline_severity = float(payload.get("decline_severity", 1.0))
        iq_growth_factor = float(payload.get("iq_growth_factor", 1.0))

        peak_age = max(23, min(35, peak_age))
        decline_onset_age = max(peak_age, min(40, decline_onset_age))
        decline_severity = max(0.6, min(1.6, decline_severity))
        iq_growth_factor = max(0.6, min(1.6, iq_growth_factor))
        return cls(
            peak_age=peak_age,
            decline_onset_age=decline_onset_age,
            decline_severity=decline_severity,
            iq_growth_factor=iq_growth_factor,
        )


@dataclass
class Boxer:
    profile: BoxerProfile
    stats: Stats
    division: str
    record: CareerRecord = field(default_factory=CareerRecord)
    amateur_points: int = 0
    popularity: int = 10
    fatigue: int = 0
    experience_points: int = 0
    injury_risk: int = 0
    aging_profile: AgingProfile = field(
        default_factory=lambda: AgingProfile(
            peak_age=28,
            decline_onset_age=30,
            decline_severity=1.0,
            iq_growth_factor=1.0,
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "stats": self.stats.to_dict(),
            "division": self.division,
            "record": self.record.to_dict(),
            "amateur_points": self.amateur_points,
            "popularity": self.popularity,
            "fatigue": self.fatigue,
            "experience_points": self.experience_points,
            "injury_risk": self.injury_risk,
            "aging_profile": self.aging_profile.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Boxer":
        record = CareerRecord.from_dict(payload.get("record", {}))
        experience_raw = payload.get("experience_points")
        if experience_raw is None:
            inferred_fights = record.wins + record.losses + record.draws
            inferred_experience = max(0, inferred_fights * 4)
        else:
            inferred_experience = max(0, int(experience_raw))

        aging_payload = payload.get("aging_profile")
        if isinstance(aging_payload, dict):
            aging_profile = AgingProfile.from_dict(aging_payload)
        else:
            from boxing_game.modules.aging_engine import generate_aging_profile

            profile_payload = payload.get("profile", {})
            height_ft = int(profile_payload.get("height_ft", 5))
            height_in = int(profile_payload.get("height_in", 10))
            weight_lbs = int(profile_payload.get("weight_lbs", 147))
            height_inches = (height_ft * 12) + height_in
            aging_profile = generate_aging_profile(
                name=str(profile_payload.get("name", "Legacy Boxer")),
                stance=str(profile_payload.get("stance", "orthodox")),
                height_inches=height_inches,
                weight_lbs=weight_lbs,
            )

        return cls(
            profile=BoxerProfile.from_dict(payload["profile"]),
            stats=Stats.from_dict(payload["stats"]),
            division=str(payload["division"]),
            record=record,
            amateur_points=int(payload.get("amateur_points", 0)),
            popularity=int(payload.get("popularity", 10)),
            fatigue=int(payload.get("fatigue", 0)),
            experience_points=inferred_experience,
            injury_risk=max(0, min(100, int(payload.get("injury_risk", 0)))),
            aging_profile=aging_profile,
        )


@dataclass
class Opponent:
    name: str
    age: int
    stance: str
    height_ft: int
    height_in: int
    weight_lbs: int
    division: str
    stats: Stats
    rating: int
    record: CareerRecord = field(default_factory=CareerRecord)
    ranking_position: int | None = None
    organization_ranks: dict[str, int | None] = field(default_factory=dict)
    is_lineal_champion: bool = False

    @property
    def height_inches(self) -> int:
        return self.height_ft * 12 + self.height_in

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "age": self.age,
            "stance": self.stance,
            "height_ft": self.height_ft,
            "height_in": self.height_in,
            "weight_lbs": self.weight_lbs,
            "division": self.division,
            "stats": self.stats.to_dict(),
            "rating": self.rating,
            "record": self.record.to_dict(),
            "ranking_position": self.ranking_position,
            "organization_ranks": self.organization_ranks,
            "is_lineal_champion": self.is_lineal_champion,
        }


@dataclass
class FightResult:
    winner: str
    method: str
    rounds_completed: int
    scorecards: list[str]
    round_log: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "winner": self.winner,
            "method": self.method,
            "rounds_completed": self.rounds_completed,
            "scorecards": self.scorecards,
            "round_log": self.round_log,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FightResult":
        return cls(
            winner=str(payload["winner"]),
            method=str(payload["method"]),
            rounds_completed=int(payload["rounds_completed"]),
            scorecards=list(payload.get("scorecards", [])),
            round_log=list(payload.get("round_log", [])),
        )


@dataclass
class FightHistoryEntry:
    opponent_name: str
    opponent_rating: int
    result: FightResult
    stage: str = "amateur"
    purse: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opponent_name": self.opponent_name,
            "opponent_rating": self.opponent_rating,
            "result": self.result.to_dict(),
            "stage": self.stage,
            "purse": self.purse,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FightHistoryEntry":
        return cls(
            opponent_name=str(payload["opponent_name"]),
            opponent_rating=int(payload["opponent_rating"]),
            result=FightResult.from_dict(payload["result"]),
            stage=str(payload.get("stage", "amateur")),
            purse=float(payload.get("purse", 0.0)),
            notes=str(payload.get("notes", "")),
        )


@dataclass
class AmateurProgress:
    fights_taken: int = 0
    tier: str = "novice"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fights_taken": self.fights_taken,
            "tier": self.tier,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AmateurProgress":
        return cls(
            fights_taken=int(payload.get("fights_taken", 0)),
            tier=str(payload.get("tier", "novice")),
        )


@dataclass
class ProCareer:
    is_active: bool = False
    promoter: str = ""
    organization_focus: str = "WBC"
    rankings: dict[str, int | None] = field(default_factory=dict)
    organization_champions: dict[str, dict[str, str | None]] = field(default_factory=dict)
    organization_defenses: dict[str, dict[str, int]] = field(default_factory=dict)
    record: CareerRecord = field(default_factory=CareerRecord)
    purse_balance: float = 0.0
    total_earnings: float = 0.0
    staff_levels: dict[str, int] = field(default_factory=dict)
    lineal_champions: dict[str, str | None] = field(default_factory=dict)
    lineal_defenses: dict[str, int] = field(default_factory=dict)
    division_changes: int = 0
    divisions_fought: list[str] = field(default_factory=list)
    last_world_news: list[str] = field(default_factory=list)
    last_player_fight_month: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_active": self.is_active,
            "promoter": self.promoter,
            "organization_focus": self.organization_focus,
            "rankings": self.rankings,
            "organization_champions": self.organization_champions,
            "organization_defenses": self.organization_defenses,
            "record": self.record.to_dict(),
            "purse_balance": self.purse_balance,
            "total_earnings": self.total_earnings,
            "staff_levels": self.staff_levels,
            "lineal_champions": self.lineal_champions,
            "lineal_defenses": self.lineal_defenses,
            "division_changes": self.division_changes,
            "divisions_fought": self.divisions_fought,
            "last_world_news": self.last_world_news,
            "last_player_fight_month": self.last_player_fight_month,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProCareer":
        raw_rankings = payload.get("rankings", {})
        rankings: dict[str, int | None] = {}
        if isinstance(raw_rankings, dict):
            for org_name, rank in raw_rankings.items():
                rankings[str(org_name)] = None if rank is None else int(rank)

        raw_staff_levels = payload.get("staff_levels", {})
        staff_levels: dict[str, int] = {}
        if isinstance(raw_staff_levels, dict):
            for staff_key, level in raw_staff_levels.items():
                staff_levels[str(staff_key)] = max(0, int(level))

        raw_lineal = payload.get("lineal_champions", {})
        lineal_champions: dict[str, str | None] = {}
        if isinstance(raw_lineal, dict):
            for division, champion in raw_lineal.items():
                if champion is None:
                    lineal_champions[str(division)] = None
                else:
                    champion_name = str(champion).strip()
                    lineal_champions[str(division)] = champion_name or None

        raw_defenses = payload.get("lineal_defenses", {})
        lineal_defenses: dict[str, int] = {}
        if isinstance(raw_defenses, dict):
            for division, defenses in raw_defenses.items():
                lineal_defenses[str(division)] = max(0, int(defenses))

        raw_divisions_fought = payload.get("divisions_fought", [])
        divisions_fought: list[str] = []
        if isinstance(raw_divisions_fought, list):
            for division in raw_divisions_fought:
                normalized = str(division).strip()
                if normalized and normalized not in divisions_fought:
                    divisions_fought.append(normalized)

        raw_org_champions = payload.get("organization_champions", {})
        organization_champions: dict[str, dict[str, str | None]] = {}
        if isinstance(raw_org_champions, dict):
            for org_name, per_division in raw_org_champions.items():
                org_key = str(org_name).strip().upper()
                if not org_key or not isinstance(per_division, dict):
                    continue
                normalized_divisions: dict[str, str | None] = {}
                for division, champion in per_division.items():
                    division_name = str(division).strip().lower()
                    if not division_name:
                        continue
                    if champion is None:
                        normalized_divisions[division_name] = None
                    else:
                        champion_name = str(champion).strip()
                        normalized_divisions[division_name] = champion_name or None
                organization_champions[org_key] = normalized_divisions

        raw_org_defenses = payload.get("organization_defenses", {})
        organization_defenses: dict[str, dict[str, int]] = {}
        if isinstance(raw_org_defenses, dict):
            for org_name, per_division in raw_org_defenses.items():
                org_key = str(org_name).strip().upper()
                if not org_key or not isinstance(per_division, dict):
                    continue
                normalized_divisions: dict[str, int] = {}
                for division, defenses in per_division.items():
                    division_name = str(division).strip().lower()
                    if not division_name:
                        continue
                    normalized_divisions[division_name] = max(0, int(defenses))
                organization_defenses[org_key] = normalized_divisions

        raw_world_news = payload.get("last_world_news", [])
        last_world_news: list[str] = []
        if isinstance(raw_world_news, list):
            for entry in raw_world_news[-20:]:
                text = str(entry).strip()
                if text:
                    last_world_news.append(text)

        return cls(
            is_active=bool(payload.get("is_active", False)),
            promoter=str(payload.get("promoter", "")),
            organization_focus=str(payload.get("organization_focus", "WBC")),
            rankings=rankings,
            organization_champions=organization_champions,
            organization_defenses=organization_defenses,
            record=CareerRecord.from_dict(payload.get("record", {})),
            purse_balance=float(payload.get("purse_balance", 0.0)),
            total_earnings=float(payload.get("total_earnings", 0.0)),
            staff_levels=staff_levels,
            lineal_champions=lineal_champions,
            lineal_defenses=lineal_defenses,
            division_changes=max(0, int(payload.get("division_changes", 0))),
            divisions_fought=divisions_fought,
            last_world_news=last_world_news,
            last_player_fight_month=max(0, int(payload.get("last_player_fight_month", 0))),
        )


@dataclass
class CareerState:
    boxer: Boxer
    month: int = 1
    year: int = 1
    career_months: int = 0
    amateur_progress: AmateurProgress = field(default_factory=AmateurProgress)
    pro_career: ProCareer = field(default_factory=ProCareer)
    history: list[FightHistoryEntry] = field(default_factory=list)
    is_retired: bool = False
    retirement_age: int | None = None
    retirement_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "boxer": self.boxer.to_dict(),
            "month": self.month,
            "year": self.year,
            "career_months": self.career_months,
            "amateur_progress": self.amateur_progress.to_dict(),
            "pro_career": self.pro_career.to_dict(),
            "history": [entry.to_dict() for entry in self.history],
            "is_retired": self.is_retired,
            "retirement_age": self.retirement_age,
            "retirement_reason": self.retirement_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CareerState":
        raw_month = int(payload.get("month", 1))
        raw_year = int(payload.get("year", 1))
        month = raw_month if 1 <= raw_month <= 12 else 1
        year = raw_year if raw_year >= 1 else 1
        raw_career_months = payload.get("career_months")
        if raw_career_months is None:
            inferred_career_months = max(0, ((year - 1) * 12) + (month - 1))
        else:
            inferred_career_months = max(0, int(raw_career_months))

        pro_career = ProCareer.from_dict(payload.get("pro_career", {}))
        boxer_payload = payload["boxer"]
        boxer = Boxer.from_dict(boxer_payload)
        if "experience_points" not in boxer_payload:
            from boxing_game.modules.experience_engine import infer_points_from_total_fights

            total_fights = (
                boxer.record.wins
                + boxer.record.losses
                + boxer.record.draws
                + pro_career.record.wins
                + pro_career.record.losses
                + pro_career.record.draws
            )
            boxer.experience_points = infer_points_from_total_fights(total_fights)

        expected_age = STARTING_AGE + (inferred_career_months // 12)
        if boxer.profile.age < expected_age:
            boxer.profile.age = expected_age

        return cls(
            boxer=boxer,
            month=month,
            year=year,
            career_months=inferred_career_months,
            amateur_progress=AmateurProgress.from_dict(payload.get("amateur_progress", {})),
            pro_career=pro_career,
            history=[
                FightHistoryEntry.from_dict(entry)
                for entry in payload.get("history", [])
            ],
            is_retired=bool(payload.get("is_retired", False)),
            retirement_age=(
                None
                if payload.get("retirement_age") is None
                else max(0, int(payload.get("retirement_age")))
            ),
            retirement_reason=str(payload.get("retirement_reason", "")),
        )
