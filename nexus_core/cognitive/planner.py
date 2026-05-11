"""
ZEUS Cognitive Core — Action Planner.

Creates deterministic execution plans from cognitive goals.
Each plan is a sequence of steps with risk classification.
No LLM dependency — plans are built from heuristic rules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from nexus_core.observability import get_logger, log_event

logger = get_logger("zeus.cognitive.planner")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


VALID_ACTION_TYPES = {"read", "write", "command", "api", "memory", "suggestion"}
VALID_RISKS = {"low", "medium", "high", "critical"}


@dataclass
class PlanStep:
    step: int
    action_type: str = "read"
    description: str = ""
    command: str | None = None
    risk: str = "low"
    requires_confirmation: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CognitivePlan:
    id: str
    goal_id: str
    steps: list[PlanStep] = field(default_factory=list)
    risk_summary: str = ""
    expected_outcome: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @property
    def max_risk(self) -> str:
        """Return the highest risk level among all steps."""
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        highest = "low"
        for step in self.steps:
            if risk_order.get(step.risk, 0) > risk_order.get(highest, 0):
                highest = step.risk
        return highest


class CognitivePlanner:
    """Creates plans from goals using deterministic heuristics."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    def create_plan(self, goal) -> CognitivePlan:
        """Generate a plan for the given goal based on its type and description."""
        goal_dict = goal.to_dict() if hasattr(goal, "to_dict") else goal
        goal_id = goal_dict.get("id", "unknown")
        goal_type = goal_dict.get("type", "operational")
        title = goal_dict.get("title", "")
        description = goal_dict.get("description", "")

        steps = self._generate_steps(goal_type, title, description)

        plan = CognitivePlan(
            id=uuid.uuid4().hex[:12],
            goal_id=goal_id,
            steps=steps,
            risk_summary=self._summarize_risk(steps),
            expected_outcome=f"Resolver: {title}",
            created_at=_now_iso(),
        )

        log_event(
            logger,
            20,
            "plan_created",
            plan_id=plan.id,
            goal_id=goal_id,
            step_count=len(steps),
            max_risk=plan.max_risk,
        )
        return plan

    def _generate_steps(
        self, goal_type: str, title: str, description: str
    ) -> list[PlanStep]:
        """Build steps based on goal type and content analysis."""
        title_lower = title.lower()
        desc_lower = description.lower()
        combined = f"{title_lower} {desc_lower}"

        steps: list[PlanStep] = []

        # All plans start with a diagnostic/read step
        steps.append(
            PlanStep(
                step=1,
                action_type="read",
                description="Coletar dados do sistema relevantes para diagnóstico",
                risk="low",
            )
        )

        if goal_type == "security":
            steps.extend(self._security_steps(combined))
        elif goal_type == "performance":
            steps.extend(self._performance_steps(combined))
        elif goal_type == "maintenance":
            steps.extend(self._maintenance_steps(combined))
        elif goal_type == "cognitive":
            steps.extend(self._cognitive_steps(combined))
        else:
            steps.extend(self._operational_steps(combined))

        # Renumber steps
        for i, step in enumerate(steps):
            step.step = i + 1

        return steps

    def _security_steps(self, context: str) -> list[PlanStep]:
        steps = [
            PlanStep(
                step=0,
                action_type="read",
                description="Analisar logs de segurança recentes",
                risk="low",
            ),
            PlanStep(
                step=0,
                action_type="memory",
                description="Consultar memória para incidentes similares",
                risk="low",
            ),
            PlanStep(
                step=0,
                action_type="suggestion",
                description="Gerar recomendações de segurança",
                risk="low",
            ),
        ]
        if "permiss" in context or "chmod" in context:
            steps.append(
                PlanStep(
                    step=0,
                    action_type="command",
                    description="Verificar permissões do diretório afetado",
                    command="ls -la",
                    risk="low",
                )
            )
        return steps

    def _performance_steps(self, context: str) -> list[PlanStep]:
        steps = [
            PlanStep(
                step=0,
                action_type="command",
                description="Coletar métricas de uso de recursos",
                command="ps aux --sort=-%mem | head -20",
                risk="low",
            ),
            PlanStep(
                step=0,
                action_type="memory",
                description="Comparar com padrões históricos",
                risk="low",
            ),
        ]
        if "ram" in context or "memória" in context:
            steps.append(
                PlanStep(
                    step=0,
                    action_type="command",
                    description="Verificar uso detalhado de RAM",
                    command="free -h",
                    risk="low",
                )
            )
        if "disk" in context or "disco" in context:
            steps.append(
                PlanStep(
                    step=0,
                    action_type="command",
                    description="Verificar uso de disco",
                    command="df -h",
                    risk="low",
                )
            )
        steps.append(
            PlanStep(
                step=0,
                action_type="suggestion",
                description="Sugerir ações para otimização de desempenho",
                risk="low",
            )
        )
        return steps

    def _maintenance_steps(self, context: str) -> list[PlanStep]:
        steps = [
            PlanStep(
                step=0,
                action_type="read",
                description="Verificar estado atual do componente",
                risk="low",
            ),
        ]
        if "systemd" in context or "service" in context:
            steps.append(
                PlanStep(
                    step=0,
                    action_type="command",
                    description="Verificar status do serviço",
                    command="systemctl --user status",
                    risk="low",
                )
            )
        if "log" in context:
            steps.append(
                PlanStep(
                    step=0,
                    action_type="command",
                    description="Verificar logs recentes",
                    command="journalctl --user -n 50 --no-pager",
                    risk="low",
                )
            )
        steps.append(
            PlanStep(
                step=0,
                action_type="suggestion",
                description="Propor ações de manutenção necessárias",
                risk="low",
            )
        )
        return steps

    def _cognitive_steps(self, context: str) -> list[PlanStep]:
        return [
            PlanStep(
                step=0,
                action_type="memory",
                description="Consultar base de conhecimento",
                risk="low",
            ),
            PlanStep(
                step=0,
                action_type="read",
                description="Analisar contexto operacional atual",
                risk="low",
            ),
            PlanStep(
                step=0,
                action_type="suggestion",
                description="Gerar insight cognitivo",
                risk="low",
            ),
        ]

    def _operational_steps(self, context: str) -> list[PlanStep]:
        steps = [
            PlanStep(
                step=0,
                action_type="read",
                description="Diagnosticar estado do componente afetado",
                risk="low",
            ),
        ]
        if "criar" in context or "create" in context:
            steps.append(
                PlanStep(
                    step=0,
                    action_type="write",
                    description="Criar recurso necessário",
                    risk="medium",
                    requires_confirmation=True,
                )
            )
        if "investigar" in context or "investigate" in context or "falha" in context:
            steps.append(
                PlanStep(
                    step=0,
                    action_type="command",
                    description="Executar diagnóstico adicional",
                    command="echo 'diagnostic placeholder'",
                    risk="low",
                )
            )
        steps.append(
            PlanStep(
                step=0,
                action_type="suggestion",
                description="Resumir descobertas e propor próximos passos",
                risk="low",
            )
        )
        return steps

    @staticmethod
    def _summarize_risk(steps: list[PlanStep]) -> str:
        risks = [s.risk for s in steps]
        if "critical" in risks:
            return "Plano contém etapas CRÍTICAS que exigem confirmação."
        if "high" in risks:
            return "Plano contém etapas de alto risco."
        if "medium" in risks:
            return "Plano com risco moderado."
        return "Plano de baixo risco — seguro para execução automática."
