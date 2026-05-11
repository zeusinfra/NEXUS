from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class AutonomyMode(str, Enum):
    SAFE = "SAFE"
    DEV = "DEV"
    AUTONOMOUS = "AUTONOMOUS"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def score(self) -> float:
        return {
            RiskLevel.LOW: 0.1,
            RiskLevel.MEDIUM: 0.35,
            RiskLevel.HIGH: 0.7,
            RiskLevel.CRITICAL: 1.2,
        }[self]


class DecisionType(str, Enum):
    ACT = "act"
    WAIT = "wait"
    CONFIRM = "confirm"


EventKind = Literal["fs", "os", "user", "system"]


@dataclass(slots=True)
class Event:
    kind: EventKind
    ts: float
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    relevance: float = 0.0


@dataclass(slots=True)
class Situation:
    ts: float
    label: str
    events: list[Event]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Goal:
    id: str
    descricao: str
    prioridade: float
    estado: Literal["ativo", "pausado", "concluido"] = "ativo"
    progresso: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlanStep:
    step: int
    description: str
    action: dict[str, Any]
    estimated_risk: RiskLevel = RiskLevel.MEDIUM
    estimated_impact: float = 0.3


@dataclass(slots=True)
class Plan:
    goal_id: str
    objective: str
    steps: list[PlanStep]
    estimated_risk: RiskLevel
    expected_impact: float
    created_ts: float
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Decision:
    kind: DecisionType
    reason: str
    expected_reward: float
    plan: Plan | None = None
    requires_confirmation: bool = False
