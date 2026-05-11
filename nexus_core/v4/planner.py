from __future__ import annotations

import json
import re
import time
from typing import Any

from nexus_core.core_system import call_cloud_llm
from nexus_core.v4.types import Goal, Plan, PlanStep, RiskLevel


_PROMPT = """Você é o PLANNER do NEXUS v4.0 (SO cognitivo).
Crie um plano multi-step para um objetivo contínuo.

Requisitos:
- Retorne APENAS JSON válido.
- Máx 6 steps.
- Cada step deve conter:
  - step (int)
  - description (string)
  - action: {"type":"cmd","command":"..."} OU {"type":"file","op":"...","path":"...","content":"..."}
  - estimated_risk: low|medium|high|critical
  - estimated_impact: 0..1
- O plano deve conter:
  - objective (string)
  - estimated_risk (low|medium|high|critical)
  - expected_impact (0..1)

Contexto:
- Você está em Linux.
- Segurança é prioridade.
- Prefira ações de diagnóstico e sugestões antes de mudanças.
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    if not raw:
        raise ValueError("empty")
    try:
        return json.loads(raw)
    except Exception:
        left = raw.find("{")
        right = raw.rfind("}")
        if left != -1 and right != -1 and right > left:
            return json.loads(raw[left : right + 1])
        raise


def _risk(value: str) -> RiskLevel:
    v = (value or "").strip().lower()
    return {
        "low": RiskLevel.LOW,
        "medium": RiskLevel.MEDIUM,
        "high": RiskLevel.HIGH,
        "critical": RiskLevel.CRITICAL,
    }.get(v, RiskLevel.MEDIUM)


def _clamp01(value: Any, default: float = 0.3) -> float:
    try:
        v = float(value)
    except Exception:
        return default
    return max(0.0, min(1.0, v))


class MultiStepPlanner:
    def __init__(self, *, llm_enabled: bool = True):
        self.llm_enabled = llm_enabled

    def plan(self, goal: Goal, *, context: str) -> Plan:
        if self.llm_enabled:
            try:
                payload = self._plan_llm(goal, context=context)
                return self._to_plan(goal, payload)
            except Exception:
                pass
        return self._fallback_plan(goal)

    def _plan_llm(self, goal: Goal, *, context: str) -> dict[str, Any]:
        user = f"Objetivo persistente: {goal.descricao}\nProgresso atual: {goal.progresso}\n\nContexto:\n{context}"
        raw = call_cloud_llm(
            [{"role": "system", "content": _PROMPT}, {"role": "user", "content": user}]
        )
        return _extract_json(raw)

    def _to_plan(self, goal: Goal, payload: dict[str, Any]) -> Plan:
        objective = str(payload.get("objective") or goal.descricao).strip()
        expected_impact = _clamp01(payload.get("expected_impact"), default=0.4)
        est_risk = _risk(str(payload.get("estimated_risk") or "medium"))
        steps_payload = (
            payload.get("steps") if isinstance(payload.get("steps"), list) else []
        )
        steps: list[PlanStep] = []
        for i, s in enumerate(steps_payload[:6], start=1):
            if not isinstance(s, dict):
                continue
            action = s.get("action") if isinstance(s.get("action"), dict) else {}
            steps.append(
                PlanStep(
                    step=int(s.get("step") or i),
                    description=str(s.get("description") or "").strip() or f"Step {i}",
                    action=action,
                    estimated_risk=_risk(str(s.get("estimated_risk") or "medium")),
                    estimated_impact=_clamp01(s.get("estimated_impact"), default=0.3),
                )
            )
        if not steps:
            steps = self._fallback_plan(goal).steps
        return Plan(
            goal_id=goal.id,
            objective=objective,
            steps=steps,
            estimated_risk=est_risk,
            expected_impact=expected_impact,
            created_ts=time.time(),
        )

    def _fallback_plan(self, goal: Goal) -> Plan:
        steps = [
            PlanStep(
                step=1,
                description="Diagnosticar pressão do sistema e processos mais pesados",
                action={
                    "type": "cmd",
                    "command": "ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head",
                },
                estimated_risk=RiskLevel.LOW,
                estimated_impact=0.25,
            ),
            PlanStep(
                step=2,
                description="Listar arquivos grandes no diretório do projeto",
                action={"type": "cmd", "command": "du -ah . | sort -hr | head"},
                estimated_risk=RiskLevel.LOW,
                estimated_impact=0.3,
            ),
        ]
        return Plan(
            goal_id=goal.id,
            objective=goal.descricao,
            steps=steps,
            estimated_risk=RiskLevel.MEDIUM,
            expected_impact=0.35,
            created_ts=time.time(),
            meta={"fallback": True},
        )
