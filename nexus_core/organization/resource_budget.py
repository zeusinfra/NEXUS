from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency fallback
    psutil = None


@dataclass(frozen=True)
class ExecutionBudget:
    cpu_soft_limit_percent: float = 85.0
    ram_soft_limit_percent: float = 88.0
    concurrent_task_limit: int = 2
    token_budget: int = 120_000
    timeout_max_s: int = 300
    block_on_resource_pressure: bool = False

    @classmethod
    def from_env(cls) -> "ExecutionBudget":
        return cls(
            cpu_soft_limit_percent=_float_env("NEXUS_EXEC_CPU_SOFT_LIMIT", 85.0),
            ram_soft_limit_percent=_float_env("NEXUS_EXEC_RAM_SOFT_LIMIT", 88.0),
            concurrent_task_limit=max(1, _int_env("NEXUS_EXEC_CONCURRENT_LIMIT", 2)),
            token_budget=max(1, _int_env("NEXUS_EXEC_TOKEN_BUDGET", 120_000)),
            timeout_max_s=max(1, _int_env("NEXUS_EXEC_TIMEOUT_MAX_SEC", 300)),
            block_on_resource_pressure=_bool_env(
                "NEXUS_EXEC_BLOCK_ON_RESOURCE_PRESSURE", False
            ),
        )


class ResourceBudgetGovernor:
    """Small execution governor for safe local autonomy."""

    def __init__(self, budget: ExecutionBudget | None = None) -> None:
        self.budget = budget or ExecutionBudget.from_env()

    def assess(
        self,
        *,
        active_executions: int,
        requested_timeout_s: int,
        estimated_tokens: int = 0,
    ) -> dict[str, Any]:
        metrics = _sample_metrics()
        effective_timeout_s = min(
            max(1, int(requested_timeout_s)), self.budget.timeout_max_s
        )
        reasons = []
        warnings = []

        if active_executions >= self.budget.concurrent_task_limit:
            reasons.append(
                "concurrent task limit reached "
                f"({active_executions}/{self.budget.concurrent_task_limit})"
            )
        if estimated_tokens > self.budget.token_budget:
            reasons.append(
                f"token budget exceeded ({estimated_tokens}/{self.budget.token_budget})"
            )
        if requested_timeout_s > self.budget.timeout_max_s:
            warnings.append(
                f"timeout capped from {requested_timeout_s}s to {effective_timeout_s}s"
            )

        cpu = metrics.get("cpu_percent")
        ram = metrics.get("ram_percent")
        pressure = False
        if cpu is not None and cpu > self.budget.cpu_soft_limit_percent:
            pressure = True
            warnings.append(f"cpu pressure {cpu:.1f}%")
        if ram is not None and ram > self.budget.ram_soft_limit_percent:
            pressure = True
            warnings.append(f"ram pressure {ram:.1f}%")
        if pressure and self.budget.block_on_resource_pressure:
            reasons.append("resource pressure exceeds configured soft budget")

        allowed = not reasons
        return {
            "allowed": allowed,
            "mode": "low_resource" if pressure else "normal",
            "reasons": reasons,
            "warnings": warnings,
            "requested_timeout_s": int(requested_timeout_s),
            "effective_timeout_s": effective_timeout_s,
            "estimated_tokens": int(estimated_tokens),
            "active_executions": int(active_executions),
            "budget": asdict(self.budget),
            "metrics": metrics,
        }


def _sample_metrics() -> dict[str, float | None]:
    if psutil is None:
        return {"cpu_percent": None, "ram_percent": None}
    return {
        "cpu_percent": float(psutil.cpu_percent(interval=None)),
        "ram_percent": float(psutil.virtual_memory().percent),
    }


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
