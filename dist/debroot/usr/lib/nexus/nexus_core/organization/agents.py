from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from nexus_core.organization.blackboard import Blackboard


@dataclass(frozen=True)
class AgentSpec:
    role: str
    department: str
    mission: str
    capabilities: tuple[str, ...]
    risk_level: str = "low"
    enabled: bool = True


@dataclass
class AgentResult:
    agent_role: str
    status: str
    summary: str
    task_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class DepartmentAgent(Protocol):
    spec: AgentSpec

    def handle(self, goal: str, blackboard: Blackboard) -> AgentResult: ...


class BasicDepartmentAgent:
    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec

    def handle(self, goal: str, blackboard: Blackboard) -> AgentResult:
        task = blackboard.create_task(
            f"{self.spec.role}: {goal[:80]}",
            owner=self.spec.role,
            goal=goal,
            metadata={"department": self.spec.department},
        )
        return AgentResult(
            agent_role=self.spec.role,
            status="queued",
            summary=f"{self.spec.role} accepted the task for planning/review.",
            task_id=task["id"],
            details={"department": self.spec.department},
        )


class CEOAgent(BasicDepartmentAgent):
    def handle(self, goal: str, blackboard: Blackboard) -> AgentResult:
        task = blackboard.create_task(
            f"CEO intake: {goal[:80]}",
            owner=self.spec.role,
            goal=goal,
            priority=1,
            metadata={"next": "planner", "department": self.spec.department},
        )
        blackboard.record_decision(
            "Goal accepted by CEO",
            "Initial organizational intake captured; Planner should break it down before execution.",
            owner=self.spec.role,
            impact="medium",
            metadata={"task_id": task["id"]},
        )
        return AgentResult(
            agent_role=self.spec.role,
            status="accepted",
            summary="Goal accepted and delegated to planning.",
            task_id=task["id"],
            details={"next": "planner"},
        )


class PlannerAgent(BasicDepartmentAgent):
    def handle(self, goal: str, blackboard: Blackboard) -> AgentResult:
        task = blackboard.create_task(
            f"Plan: {goal[:90]}",
            owner=self.spec.role,
            goal=goal,
            priority=2,
            metadata={
                "steps": [
                    "Clarify success criteria",
                    "Map files/services affected",
                    "Identify safety constraints",
                    "Create reversible implementation slice",
                ]
            },
        )
        return AgentResult(
            agent_role=self.spec.role,
            status="planned",
            summary="Initial executable plan skeleton recorded.",
            task_id=task["id"],
            details=task["metadata"],
        )


class GuardianAgent(BasicDepartmentAgent):
    def handle(self, goal: str, blackboard: Blackboard) -> AgentResult:
        task = blackboard.create_task(
            f"Guardian review: {goal[:80]}",
            owner=self.spec.role,
            goal=goal,
            priority=1,
            metadata={
                "requires_approval_for": [
                    "sudo",
                    "rm",
                    "systemd changes",
                    "sensitive file edits",
                    "destructive commands",
                ],
                "default_mode": "dry-run when possible",
            },
        )
        return AgentResult(
            agent_role=self.spec.role,
            status="guarded",
            summary="Safety review queued; execution must use policy and approval layers.",
            task_id=task["id"],
            details=task["metadata"],
        )


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, DepartmentAgent] = {}

    def register(self, agent: DepartmentAgent) -> None:
        self._agents[agent.spec.role] = agent

    def get(self, role: str) -> DepartmentAgent:
        return self._agents[role]

    def roles(self) -> list[str]:
        return sorted(self._agents)

    def specs(self) -> list[dict[str, Any]]:
        return [asdict(agent.spec) for agent in self._agents.values()]

    def sync_blackboard(self, blackboard: Blackboard) -> None:
        for spec in self.specs():
            blackboard.register_agent(spec)

    def route(self, goal: str) -> DepartmentAgent:
        text = (goal or "").lower()
        routing = [
            (
                "security",
                ("sudo", "permissao", "permissao", "risco", "seguranca", "rm "),
            ),
            ("devops", ("systemd", "docker", "podman", "ci", "deploy", "servico")),
            ("coder", ("codigo", "implementar", "refatorar", "bug", "arquivo")),
            ("reviewer", ("revisar", "review", "qualidade", "teste")),
            ("memory", ("memoria", "obsidian", "historico", "decisao")),
            ("observer", ("foco", "janela", "atividade", "modo")),
            ("cto", ("arquitetura", "stack", "design tecnico")),
            ("planner", ("plano", "planejar", "tarefas")),
        ]
        for role, terms in routing:
            if any(term in text for term in terms) and role in self._agents:
                return self._agents[role]
        return self._agents["ceo"]

    def dispatch(
        self, goal: str, blackboard: Blackboard, role: str | None = None
    ) -> AgentResult:
        agent = self._agents[role] if role else self.route(goal)
        return agent.handle(goal, blackboard)


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    specs = [
        AgentSpec(
            "ceo",
            "executive",
            "Understand goals, prioritize, and delegate.",
            ("intake", "priority", "delegation"),
        ),
        AgentSpec(
            "cto",
            "architecture",
            "Decide architecture and technical direction.",
            ("architecture", "stack", "tradeoffs"),
        ),
        AgentSpec(
            "planner",
            "planning",
            "Break goals into executable tasks.",
            ("planning", "task_breakdown", "sequencing"),
        ),
        AgentSpec(
            "coder",
            "engineering",
            "Implement code changes and refactors.",
            ("coding", "refactor", "patching"),
            risk_level="medium",
        ),
        AgentSpec(
            "reviewer",
            "quality",
            "Review code, tests, and regressions.",
            ("review", "tests", "quality"),
        ),
        AgentSpec(
            "security",
            "guardian",
            "Evaluate risk and block unsafe execution.",
            ("policy", "approval", "risk"),
            risk_level="high",
        ),
        AgentSpec(
            "devops",
            "operations",
            "Manage systemd, containers, logs, and CI.",
            ("systemd", "docker", "logs"),
            risk_level="high",
        ),
        AgentSpec(
            "memory",
            "knowledge",
            "Record decisions, history, and summaries.",
            ("memory", "summaries", "obsidian"),
        ),
        AgentSpec(
            "observer",
            "sensing",
            "Track user focus and system mode.",
            ("focus", "mode_detection", "monitoring"),
        ),
    ]
    for spec in specs:
        if spec.role == "ceo":
            registry.register(CEOAgent(spec))
        elif spec.role == "planner":
            registry.register(PlannerAgent(spec))
        elif spec.role == "security":
            registry.register(GuardianAgent(spec))
        else:
            registry.register(BasicDepartmentAgent(spec))
    return registry
