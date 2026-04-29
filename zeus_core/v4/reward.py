from __future__ import annotations

import math
from dataclasses import dataclass

from zeus_core.v4.types import RiskLevel


@dataclass(slots=True)
class RewardSignal:
    success: float  # 0..1
    impact: float  # 0..1
    risk: float  # 0..~1.2
    cost: float  # 0..1

    def total(self) -> float:
        # reward = (sucesso * impacto) - risco - custo
        return (self.success * self.impact) - self.risk - self.cost


def cost_from_runtime(seconds: float, *, cpu_avg: float | None = None) -> float:
    # custo cresce com tempo e com cpu
    t = max(0.0, float(seconds))
    base = 1.0 - math.exp(-t / 3.5)  # 0..1
    cpu = 0.0
    if cpu_avg is not None:
        try:
            cpu = max(0.0, min(1.0, float(cpu_avg) / 100.0))
        except Exception:
            cpu = 0.0
    return max(0.0, min(1.0, base * 0.75 + cpu * 0.35))


def risk_score(level: RiskLevel) -> float:
    return level.score()
