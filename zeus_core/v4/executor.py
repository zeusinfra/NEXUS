from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

import shlex
from pathlib import Path
from zeus_core.v4.guardian import RiskAssessment, SemanticGuardian
from zeus_core.v4.reward import RewardSignal, cost_from_runtime, risk_score
from zeus_core.v4.types import AutonomyMode, Decision, DecisionType, Plan, PlanStep, RiskLevel


@dataclass(slots=True)
class StepResult:
    step: int
    ok: bool
    output: str = ""
    error: str = ""
    duration_s: float = 0.0
    risk: RiskLevel = RiskLevel.MEDIUM
    impact: float = 0.0


class ShadowExecutor:
    def __init__(self, *, mode: AutonomyMode):
        self.mode = mode
        self.guardian = SemanticGuardian(mode=mode)
        self.shadow_root = Path(os.getenv("ZEUS_SHADOW_ROOT", "/tmp/zeus_shadow"))
        self.shadow_root.mkdir(parents=True, exist_ok=True)
        self.enable_real = os.getenv("ZEUS_V4_ENABLE_REAL_EXECUTION", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.allowlist = {
            tok.strip()
            for tok in os.getenv("ZEUS_V4_CMD_ALLOWLIST", "ls,ps,du,df,free,uptime,whoami,id,uname").split(",")
            if tok.strip()
        }

    def decide(self, plan: Plan) -> Decision:
        worst = plan.estimated_risk
        exp_reward = max(-2.0, min(2.0, (plan.expected_impact * 0.6) - risk_score(worst)))
        assess_confirm = self.guardian.requires_confirmation(
            RiskAssessment(level=worst, reason="risco do plano", intent="plan")
        )
        if self.mode == AutonomyMode.SAFE:
            return Decision(
                kind=DecisionType.ACT,
                reason="SAFE: executar somente em shadow (simulação)",
                expected_reward=exp_reward,
                plan=plan,
                requires_confirmation=False,
            )
        if assess_confirm:
            return Decision(
                kind=DecisionType.CONFIRM,
                reason=f"Risco {worst.value} exige confirmação",
                expected_reward=exp_reward,
                plan=plan,
                requires_confirmation=True,
            )
        return Decision(kind=DecisionType.ACT, reason="Risco aceitável", expected_reward=exp_reward, plan=plan)

    async def run_plan_shadow(self, plan: Plan) -> tuple[list[StepResult], RewardSignal]:
        results: list[StepResult] = []
        overall_success = 1.0
        avg_impact = 0.0
        worst_risk = RiskLevel.LOW
        t0 = time.time()

        for step in plan.steps:
            r = await self._run_step_shadow(step)
            results.append(r)
            avg_impact += r.impact
            if r.risk.score() > worst_risk.score():
                worst_risk = r.risk
            if not r.ok:
                overall_success = 0.0
                break
            # execução real opcional (muito restrita) após shadow OK
            if self.enable_real and self.mode != AutonomyMode.SAFE:
                real_ok = await self._maybe_execute_real(step, r)
                if not real_ok:
                    overall_success = 0.0
                    break

        dt = time.time() - t0
        avg_impact = (avg_impact / max(1, len(results))) if results else 0.0
        reward = RewardSignal(
            success=overall_success,
            impact=max(avg_impact, plan.expected_impact),
            risk=risk_score(worst_risk),
            cost=cost_from_runtime(dt),
        )
        return results, reward

    async def _run_step_shadow(self, step: PlanStep) -> StepResult:
        action = step.action or {}
        assessment = self.guardian.assess_action(action)
        t0 = time.time()

        a_type = (action.get("type") or "").strip().lower()
        if a_type == "cmd":
            cmd = str(action.get("command") or "").strip()
            if not cmd:
                return StepResult(step=step.step, ok=True, duration_s=0.0, risk=assessment.level, impact=step.estimated_impact)
            sim = await self._simulate_shell(cmd)
            dt = time.time() - t0
            return StepResult(
                step=step.step,
                ok=bool(sim.get("success")),
                output=str(sim.get("output") or "")[:2000],
                error=str(sim.get("error") or "")[:800],
                duration_s=dt,
                risk=assessment.level,
                impact=step.estimated_impact,
            )

        # Fallback: ação não suportada ainda no executor shadow
        dt = time.time() - t0
        return StepResult(
            step=step.step,
            ok=False,
            output="",
            error=f"Ação não suportada no shadow executor: {a_type or 'unknown'}",
            duration_s=dt,
            risk=assessment.level,
            impact=0.0,
        )

    async def _maybe_execute_real(self, step: PlanStep, shadow_result: StepResult) -> bool:
        action = step.action or {}
        a_type = (action.get("type") or "").strip().lower()
        if a_type != "cmd":
            return True
        assessment = self.guardian.assess_action(action)
        if assessment.level != RiskLevel.LOW:
            return True
        cmd = str(action.get("command") or "").strip()
        if not cmd:
            return True
        argv = shlex.split(cmd)
        if not argv:
            return True
        if argv[0] not in self.allowlist:
            return False
        try:
            timeout_s = float(os.getenv("ZEUS_V4_REAL_TIMEOUT_SEC", "12"))
        except Exception:
            timeout_s = 12.0
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.shadow_root),
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return False
        except Exception:
            return False
        return proc.returncode == 0

    async def _simulate_shell(self, command: str) -> dict[str, Any]:
        try:
            timeout_s = float(os.getenv("ZEUS_V4_SHADOW_TIMEOUT_SEC", "10"))
        except Exception:
            timeout_s = 10.0

        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self.shadow_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"success": False, "confidence": 0.0, "output": "", "error": "Simulation Timeout", "return_code": None}

        success = proc.returncode == 0
        out_s = (out or b"").decode(errors="ignore")
        err_s = (err or b"").decode(errors="ignore")
        score = 0.0
        if success:
            score += 0.4
        if not err_s.strip():
            score += 0.3
        if success and out_s.strip():
            score += 0.3
        return {"success": success, "confidence": score, "output": out_s, "error": err_s, "return_code": proc.returncode}
