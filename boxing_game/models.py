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
class Boxer:
    profile: BoxerProfile
    stats: Stats
    division: str
    record: CareerRecord = field(default_factory=CareerRecord)
    amateur_points: int = 0
    popularity: int = 10
    fatigue: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "stats": self.stats.to_dict(),
            "division": self.division,
            "record": self.record.to_dict(),
            "amateur_points": self.amateur_points,
            "popularity": self.popularity,
            "fatigue": self.fatigue,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Boxer":
        return cls(
            profile=BoxerProfile.from_dict(payload["profile"]),
            stats=Stats.from_dict(payload["stats"]),
            division=str(payload["division"]),
            record=CareerRecord.from_dict(payload.get("record", {})),
            amateur_points=int(payload.get("amateur_points", 0)),
            popularity=int(payload.get("popularity", 10)),
            fatigue=int(payload.get("fatigue", 0)),
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "opponent_name": self.opponent_name,
            "opponent_rating": self.opponent_rating,
            "result": self.result.to_dict(),
            "stage": self.stage,
            "purse": self.purse,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FightHistoryEntry":
        return cls(
            opponent_name=str(payload["opponent_name"]),
            opponent_rating=int(payload["opponent_rating"]),
            result=FightResult.from_dict(payload["result"]),
            stage=str(payload.get("stage", "amateur")),
            purse=float(payload.get("purse", 0.0)),
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
    record: CareerRecord = field(default_factory=CareerRecord)
    purse_balance: float = 0.0
    total_earnings: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_active": self.is_active,
            "promoter": self.promoter,
            "organization_focus": self.organization_focus,
            "rankings": self.rankings,
            "record": self.record.to_dict(),
            "purse_balance": self.purse_balance,
            "total_earnings": self.total_earnings,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProCareer":
        raw_rankings = payload.get("rankings", {})
        rankings: dict[str, int | None] = {}
        if isinstance(raw_rankings, dict):
            for org_name, rank in raw_rankings.items():
                rankings[str(org_name)] = None if rank is None else int(rank)

        return cls(
            is_active=bool(payload.get("is_active", False)),
            promoter=str(payload.get("promoter", "")),
            organization_focus=str(payload.get("organization_focus", "WBC")),
            rankings=rankings,
            record=CareerRecord.from_dict(payload.get("record", {})),
            purse_balance=float(payload.get("purse_balance", 0.0)),
            total_earnings=float(payload.get("total_earnings", 0.0)),
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "boxer": self.boxer.to_dict(),
            "month": self.month,
            "year": self.year,
            "career_months": self.career_months,
            "amateur_progress": self.amateur_progress.to_dict(),
            "pro_career": self.pro_career.to_dict(),
            "history": [entry.to_dict() for entry in self.history],
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

        boxer = Boxer.from_dict(payload["boxer"])
        expected_age = STARTING_AGE + (inferred_career_months // 12)
        if boxer.profile.age < expected_age:
            boxer.profile.age = expected_age

        return cls(
            boxer=boxer,
            month=month,
            year=year,
            career_months=inferred_career_months,
            amateur_progress=AmateurProgress.from_dict(payload.get("amateur_progress", {})),
            pro_career=ProCareer.from_dict(payload.get("pro_career", {})),
            history=[
                FightHistoryEntry.from_dict(entry)
                for entry in payload.get("history", [])
            ],
        )
