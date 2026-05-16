from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nexus_core.organization.agents import AgentRegistry
from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.organization.observer import ObservationSnapshot


@dataclass(frozen=True)
class AgentTickResult:
    agent_role: str
    mode: str
    status: str
    summary: str
    tick_count: int


class ContinuousAgentRuntime:
    """Keeps department agents represented as continuously ticking workers."""

    def __init__(
        self,
        registry: AgentRegistry,
        blackboard: Blackboard,
        memory: OrganizationalMemoryStore,
    ) -> None:
        self.registry = registry
        self.blackboard = blackboard
        self.memory = memory
        self._tick_counts: dict[str, int] = {}

    def tick_all(self, observation: ObservationSnapshot) -> list[AgentTickResult]:
        results = []
        for role in self.registry.roles():
            results.append(self.tick(role, observation))
        return results

    def tick(self, role: str, observation: ObservationSnapshot) -> AgentTickResult:
        count = self._tick_counts.get(role, 0) + 1
        self._tick_counts[role] = count
        status, summary, metadata = self._status_for(role, observation)
        self.blackboard.update_agent_status(
            role,
            status=status,
            mode=observation.mode,
            tick_count=count,
            summary=summary,
        )
        self.memory.record_agent_tick(
            agent_role=role,
            mode=observation.mode,
            status=status,
            summary=summary,
            metadata=metadata,
        )
        return AgentTickResult(
            agent_role=role,
            mode=observation.mode,
            status=status,
            summary=summary,
            tick_count=count,
        )

    def _status_for(
        self, role: str, observation: ObservationSnapshot
    ) -> tuple[str, str, dict[str, Any]]:
        metadata = {
            "confidence": observation.confidence,
            "active_window": observation.active_window,
            "triggers": observation.triggers,
        }
        if role == "observer":
            return "observing", f"Mode={observation.mode}", metadata
        if role == "security":
            return "guarding", "Approval and risk gates active.", metadata
        if role == "memory":
            return "recording", "Persisting organizational state.", metadata
        if observation.mode == "MAINTENANCE" and role == "devops":
            return "alert", "System pressure requires operational attention.", metadata
        if observation.mode == "DEVELOPMENT" and role in {
            "cto",
            "planner",
            "coder",
            "reviewer",
        }:
            return (
                "active",
                "Development context detected; engineering agents are warm.",
                metadata,
            )
        if observation.mode == "RESEARCH" and role in {"ceo", "cto", "memory"}:
            return (
                "active",
                "Research context detected; strategy/memory agents are warm.",
                metadata,
            )
        return "standby", "Heartbeat recorded.", metadata
