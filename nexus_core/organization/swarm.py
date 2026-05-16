from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from nexus_core.organization.agents import AgentRegistry, AgentResult
from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.sentry_observability import add_breadcrumb, capture_exception


@dataclass(frozen=True)
class SwarmPlanItem:
    title: str
    owner: str
    priority: int
    status: str = "queued"
    risk_level: str = "low"
    depends_on: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SwarmOrchestrator:
    """Coordinates agents through the shared blackboard.

    This layer does not bypass approval or execution controls. It turns an
    operator objective into traceable tasks, decisions, and agent state.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        blackboard: Blackboard,
        memory: OrganizationalMemoryStore,
    ) -> None:
        self.registry = registry
        self.blackboard = blackboard
        self.memory = memory

    def submit_objective(
        self,
        goal: str,
        *,
        requested_by: str = "operator",
        autonomy_level: str = "LEVEL_1",
    ) -> dict[str, Any]:
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal is required")

        objective_id = f"obj_{uuid.uuid4().hex[:12]}"
        self.registry.sync_blackboard(self.blackboard)
        self.blackboard.set_current_goal(goal)
        add_breadcrumb(
            "swarm objective received",
            category="swarm",
            data={"objective_id": objective_id, "requested_by": requested_by},
        )

        agent_results: list[AgentResult] = []
        try:
            for role in ("ceo", "planner", "security"):
                if role in self.registry.roles():
                    result = self.registry.dispatch(goal, self.blackboard, role=role)
                    agent_results.append(result)
                    add_breadcrumb(
                        "agent selected",
                        category="swarm",
                        data={
                            "objective_id": objective_id,
                            "agent_id": f"agent_{result.agent_role}",
                            "role": result.agent_role,
                            "task_id": result.task_id,
                        },
                    )
        except Exception as exc:
            self.blackboard.append_error(
                {
                    "objective_id": objective_id,
                    "module": "swarm",
                    "error": str(exc),
                }
            )
            self.memory.record_incident(
                severity="error",
                module="swarm",
                message=str(exc),
                metadata={"objective_id": objective_id, "goal": goal},
            )
            capture_exception(
                exc,
                module="swarm",
                tags={"objective_id": objective_id, "execution_status": "failed"},
            )
            raise

        plan = self._build_plan(goal)
        self.blackboard.set_plan([asdict(item) for item in plan])
        add_breadcrumb(
            "plan created",
            category="swarm",
            data={"objective_id": objective_id, "tasks": len(plan)},
        )

        tasks = []
        for item in plan:
            task = self.blackboard.create_task(
                item.title,
                owner=item.owner,
                goal=goal,
                priority=item.priority,
                status=item.status,
                metadata={
                    **item.metadata,
                    "objective_id": objective_id,
                    "risk_level": item.risk_level,
                    "depends_on": item.depends_on,
                    "success_criteria": item.success_criteria,
                },
            )
            tasks.append(task)
            self._update_agent(
                item.owner,
                status="assigned",
                current_task=task["id"],
                confidence=0.72,
                risk_level=item.risk_level,
                objective_id=objective_id,
            )

        for role in self.registry.roles():
            self._ensure_agent_persisted(role, objective_id=objective_id)

        decision = self.blackboard.record_decision(
            "Swarm objective accepted",
            "Objective was decomposed into traceable tasks. Execution must use the approved runtime and verification path.",
            owner="ceo",
            impact="high",
            metadata={
                "objective_id": objective_id,
                "requested_by": requested_by,
                "autonomy_level": autonomy_level,
                "task_ids": [task["id"] for task in tasks],
            },
        )
        self.memory.record_memory_entry(
            scope="swarm",
            kind="objective",
            content=goal,
            source=requested_by,
            metadata={
                "objective_id": objective_id,
                "autonomy_level": autonomy_level,
                "task_ids": [task["id"] for task in tasks],
            },
        )
        self.blackboard.append_event(
            "SWARM_OBJECTIVE_SUBMITTED",
            {
                "objective_id": objective_id,
                "requested_by": requested_by,
                "autonomy_level": autonomy_level,
                "tasks": len(tasks),
            },
        )
        self.blackboard.append_evidence(
            {
                "objective_id": objective_id,
                "kind": "plan",
                "task_ids": [task["id"] for task in tasks],
            }
        )

        return {
            "objective_id": objective_id,
            "goal": goal,
            "requested_by": requested_by,
            "autonomy_level": autonomy_level,
            "status": "planned",
            "agents": self.memory.list_agents(limit=100),
            "agent_results": [asdict(result) for result in agent_results],
            "plan": [asdict(item) for item in plan],
            "tasks": tasks,
            "decision": decision,
        }

    def status(self) -> dict[str, Any]:
        snapshot = self.blackboard.snapshot()
        return {
            "current_goal": snapshot.get("current_goal"),
            "plan": snapshot.get("plan", []),
            "agents": self.memory.list_agents(limit=100),
            "tasks": self.memory.list_tasks(limit=100),
            "blockers": snapshot.get("blockers", []),
            "errors": snapshot.get("errors", []),
            "partial_results": snapshot.get("partial_results", []),
            "evidence": snapshot.get("evidence", []),
            "memory": self.memory.counts(),
        }

    def _build_plan(self, goal: str) -> list[SwarmPlanItem]:
        text = goal.lower()
        items = [
            SwarmPlanItem(
                title="Define objective priority and success criteria",
                owner="ceo",
                priority=1,
                success_criteria=["final objective and constraints are explicit"],
            ),
            SwarmPlanItem(
                title="Break objective into executable tasks",
                owner="planner",
                priority=1,
                success_criteria=["tasks have owners, risks, and verification paths"],
            ),
            SwarmPlanItem(
                title="Evaluate risks and approval requirements",
                owner="security",
                priority=1,
                risk_level="high",
                success_criteria=["dangerous commands require approval before runtime"],
            ),
            SwarmPlanItem(
                title="Persist decisions and lessons in organizational memory",
                owner="memory",
                priority=3,
                success_criteria=[
                    "decisions, events, and evidence are written to SQLite"
                ],
            ),
            SwarmPlanItem(
                title="Observe Linux context and resource pressure",
                owner="observer",
                priority=3,
                success_criteria=["resource and context observations are visible"],
            ),
        ]
        if any(
            term in text
            for term in ("codigo", "code", "implementar", "refatorar", "fix")
        ):
            items.append(
                SwarmPlanItem(
                    title="Implement scoped code changes",
                    owner="coder",
                    priority=2,
                    risk_level="medium",
                    depends_on=["planner", "security"],
                    success_criteria=["diff exists and is ready for review"],
                )
            )
            items.append(
                SwarmPlanItem(
                    title="Review diff and run focused validation",
                    owner="reviewer",
                    priority=2,
                    depends_on=["coder"],
                    success_criteria=["tests or checks provide evidence"],
                )
            )
        if any(
            term in text
            for term in ("systemd", "docker", "podman", "ci", "runtime", "linux")
        ):
            items.append(
                SwarmPlanItem(
                    title="Validate runtime, services, and environment",
                    owner="devops",
                    priority=2,
                    risk_level="high",
                    depends_on=["security"],
                    success_criteria=["service/process/build evidence is captured"],
                )
            )
        if any(
            term in text
            for term in ("arquitetura", "architecture", "swarm", "multiagente")
        ):
            items.append(
                SwarmPlanItem(
                    title="Review architecture boundaries and integration points",
                    owner="cto",
                    priority=2,
                    depends_on=["planner"],
                    success_criteria=["module boundaries and contracts are documented"],
                )
            )
        return items

    def _update_agent(
        self,
        role: str,
        *,
        status: str,
        current_task: str | None,
        confidence: float,
        risk_level: str,
        objective_id: str,
    ) -> None:
        agent = self.blackboard.update_agent_status(
            role,
            status=status,
            current_task=current_task,
            confidence=confidence,
            risk_level=risk_level,
        )
        self.memory.record_agent_state(
            agent_id=agent.get("agent_id", f"agent_{role}"),
            role=role,
            status=agent.get("status", status),
            current_task=agent.get("current_task", current_task),
            confidence=float(agent.get("confidence", confidence)),
            risk_level=agent.get("risk_level", risk_level),
            permissions=list(agent.get("permissions", [])),
            memory_scope=agent.get("memory_scope", role),
            metadata={"objective_id": objective_id},
        )

    def _ensure_agent_persisted(self, role: str, *, objective_id: str) -> None:
        snapshot = self.blackboard.snapshot()
        agent = snapshot.get("agents", {}).get(role, {})
        self.memory.record_agent_state(
            agent_id=agent.get("agent_id", f"agent_{role}"),
            role=role,
            status=agent.get("status", "idle"),
            current_task=agent.get("current_task"),
            confidence=float(agent.get("confidence", 0.0)),
            risk_level=agent.get("risk_level", "low"),
            permissions=list(agent.get("permissions", [])),
            memory_scope=agent.get("memory_scope", role),
            metadata={"objective_id": objective_id},
        )
