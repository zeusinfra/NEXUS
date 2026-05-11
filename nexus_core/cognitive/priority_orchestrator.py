"""
NEXUS Cognitive Core — Priority Orchestrator.

The executive control module that decides which goals should be pursued
in the current cycle based on attention, resources, and temporal context.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List

from nexus_core.observability import get_logger, log_event

logger = get_logger("nexus.cognitive.orchestrator")

try:
    from nexus_cognitive import CognitiveEngineRust

    RUST_COGNITIVE_AVAILABLE = True
except ImportError:
    RUST_COGNITIVE_AVAILABLE = False


@dataclass
class OrchestrationResult:
    selected_goals: List[dict]
    deferred_goals: List[dict]
    rationale: str


class PriorityOrchestrator:
    """Executive control for goal prioritization."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self.max_active_goals_default = 3

        if RUST_COGNITIVE_AVAILABLE:
            self.rust_engine = CognitiveEngineRust()
        else:
            self.rust_engine = None

    def orchestrate(self, goals: List[dict], context: dict) -> OrchestrationResult:
        """
        Rank and filter goals based on the current cognitive context.
        """
        if not goals:
            return OrchestrationResult([], [], "Nenhuma meta pendente.")

        if self.rust_engine:
            try:
                # O Rust espera JSON
                goals_json = json.dumps(goals)
                context_json = json.dumps(context)
                max_active = context.get("attention", {}).get(
                    "max_active_goals", self.max_active_goals_default
                )

                res_json = self.rust_engine.orchestrate(
                    goals_json, context_json, max_active
                )
                res_dict = json.loads(res_json)

                return OrchestrationResult(
                    selected_goals=res_dict["selected"],
                    deferred_goals=res_dict["deferred"],
                    rationale=res_dict["rationale"] + " (Rust Engine)",
                )
            except Exception as e:
                logger.error(f"Erro no orquestrador Rust: {e}. Usando fallback Python.")

        # 1. Determine capacity
        capacity = self._determine_capacity(context)

        # 2. Score goals
        scored_goals = []
        for goal in goals:
            score = self._score_goal(goal, context)
            scored_goals.append((score, goal))

        # 3. Sort by score (descending)
        scored_goals.sort(key=lambda x: x[0], reverse=True)

        # 4. Select top goals within capacity
        selected = [g for _, g in scored_goals[:capacity]]
        deferred = [g for _, g in scored_goals[capacity:]]

        rationale = f"Selecionadas {len(selected)} metas de {len(goals)} totais. Capacidade: {capacity}."
        if context.get("attention", {}).get("state") == "deep_focus":
            rationale += " Foco profundo ativo: priorizando apenas o essencial."

        log_event(
            logger,
            20,
            "goals_orchestrated",
            selected_count=len(selected),
            deferred_count=len(deferred),
            capacity=capacity,
        )

        return OrchestrationResult(selected, deferred, rationale)

    def _determine_capacity(self, context: dict) -> int:
        """Determine how many goals the system should handle simultaneously."""
        attention = context.get("attention", {})
        # Attention engine already provides a 'max_active_goals' recommendation
        capacity = attention.get("max_active_goals", self.max_active_goals_default)

        # Adjust based on resource pressure
        sys = context.get("perception", {}).get("system", {})
        cpu = sys.get("cpu_percent", 0)
        ram = sys.get("ram_percent", 0)

        if cpu > 85 or ram > 90:
            capacity = max(1, capacity - 1)

        return capacity

    def _score_goal(self, goal: dict, context: dict) -> float:
        """Calculate a dynamic priority score for a goal."""
        # Base priority from goal engine (0-100)
        base_priority = float(self._goal_value(goal, "priority", 50))

        # Modifiers
        attention_state = context.get("attention", {}).get("state", "idle")
        gtype = self._goal_value(goal, "type", "operational")

        score = base_priority

        # 1. Attention Alignment
        if attention_state == "development":
            if gtype in {"technical", "operational"}:
                score *= 1.2
            elif gtype == "maintenance":
                score *= 0.8
        elif attention_state == "deep_focus":
            if gtype == "security":
                score *= 1.5
            else:
                score *= 0.5  # Suppress almost everything
        elif attention_state == "mining":
            if gtype == "maintenance":
                score *= 1.3
            else:
                score *= 0.7

        # 2. Temporal Alignment
        temporal = context.get("temporal", {})
        if temporal.get("is_late_night") and gtype == "maintenance":
            score *= 1.4  # Night is good for cleanup

        # 3. Urgency / Risk
        risk = self._goal_value(goal, "risk", "low")
        if risk == "high":
            score += 20

        return score

    @staticmethod
    def _goal_value(goal: Any, key: str, default: Any = None) -> Any:
        if isinstance(goal, dict):
            return goal.get(key, default)
        return getattr(goal, key, default)
