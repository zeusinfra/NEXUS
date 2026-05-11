"""
NEXUS Cognitive Core — Simulator.

Risk assessment engine that evaluates plans against safety policies.
Does NOT execute anything — pure analysis of command patterns and action types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from nexus_core.observability import get_logger, log_event

logger = get_logger("nexus.cognitive.simulator")


# Dangerous command patterns that must ALWAYS be blocked
BLOCKED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+(-[rRf]+\s+)*(/|\*|~|\.\.)"),  # rm -rf / or rm *
    re.compile(r"\bchmod\s+(-R|--recursive)\s"),  # recursive chmod
    re.compile(r"\bchown\s+(-R|--recursive)\s"),  # recursive chown
    re.compile(r"\bcurl\b.*\|\s*(ba)?sh"),  # curl | bash
    re.compile(r"\bwget\b.*\|\s*(ba)?sh"),  # wget | sh
    re.compile(r"\bsudo\b"),  # any sudo
    re.compile(r"\bmkfs\b"),  # filesystem format
    re.compile(r"\bdd\s+if="),  # disk destroyer
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bpoweroff\b"),
    re.compile(r"\bgit\s+push\b"),  # no auto push
    re.compile(r"\bgit\s+force"),  # no force anything
    re.compile(r">\s*\.env\b"),  # redirecting into .env
    re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE),  # SQL drops
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b.*WHERE\s+1\s*=\s*1", re.IGNORECASE),
]

# Patterns indicating elevated risk (not blocked, but requires confirmation)
HIGH_RISK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\b"),  # any rm
    re.compile(r"\bmv\b"),  # file moves
    re.compile(r"\bcp\b.*--force"),  # forced copy
    re.compile(r"\bchmod\b"),  # any permission change
    re.compile(r"\bchown\b"),  # any ownership change
    re.compile(r"\bkill\b"),  # process killing
    re.compile(r"\bpkill\b"),  # pattern killing
    re.compile(r"\bgit\s+reset"),  # git reset
    re.compile(r"\bgit\s+rebase"),  # git rebase
    re.compile(r"\bnpm\s+install\b"),  # package installs
    re.compile(r"\bpip\s+install\b"),  # pip installs
    re.compile(r"\bcargo\s+install\b"),  # cargo installs
]

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class SimulationResult:
    """Result of simulating a plan."""

    plan_id: str
    approved_for_auto_execution: bool = False
    risk: str = "low"
    blocked_reasons: list[str] = field(default_factory=list)
    safe_alternative: str = ""
    step_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class CognitiveSimulator:
    """Evaluates plans against safety policies without executing anything."""

    def simulate_plan(self, plan) -> SimulationResult:
        """Analyze every step in the plan and return an aggregated result."""
        plan_dict = plan.to_dict() if hasattr(plan, "to_dict") else plan
        plan_id = plan_dict.get("id", "unknown")
        steps = plan_dict.get("steps", [])

        step_results = []
        all_blocked: list[str] = []
        max_risk = "low"
        any_requires_confirmation = False

        for step_data in steps:
            sr = self.estimate_risk(step_data)
            step_results.append(sr)

            step_risk = sr.get("risk", "low")
            if RISK_ORDER.get(step_risk, 0) > RISK_ORDER.get(max_risk, 0):
                max_risk = step_risk

            if sr.get("blocked"):
                all_blocked.extend(sr.get("blocked_reasons", []))

            if sr.get("requires_confirmation"):
                any_requires_confirmation = True

        # Determine auto-execution approval
        approved = (
            not all_blocked
            and max_risk in {"low", "medium"}
            and not any_requires_confirmation
        )

        # For medium-risk, only auto-approve if all medium steps are read/diagnostic
        if max_risk == "medium" and not all_blocked:
            for sr in step_results:
                if sr.get("risk") == "medium" and sr.get("action_type") not in {
                    "read",
                    "memory",
                    "suggestion",
                }:
                    approved = False
                    break

        result = SimulationResult(
            plan_id=plan_id,
            approved_for_auto_execution=approved,
            risk=max_risk,
            blocked_reasons=all_blocked,
            safe_alternative=self._suggest_alternative(all_blocked)
            if all_blocked
            else "",
            step_results=step_results,
        )

        log_event(
            logger,
            20,
            "plan_simulated",
            plan_id=plan_id,
            approved=approved,
            risk=max_risk,
            blocked_count=len(all_blocked),
        )
        return result

    def estimate_risk(self, step: dict) -> dict:
        """Evaluate risk level for a single step."""
        action_type = step.get("action_type", "read")
        command = step.get("command") or ""
        risk = step.get("risk", "low")
        requires_confirmation = step.get("requires_confirmation", False)
        blocked = False
        blocked_reasons: list[str] = []

        # Command-based risk assessment
        if command:
            block_result = self._check_blocked(command)
            if block_result:
                blocked = True
                blocked_reasons.extend(block_result)
                risk = "critical"
            elif self._check_high_risk(command):
                if RISK_ORDER.get(risk, 0) < RISK_ORDER["high"]:
                    risk = "high"
                requires_confirmation = True

        # Action-type based risk
        if action_type in {"write", "command"} and not command:
            if RISK_ORDER.get(risk, 0) < RISK_ORDER["medium"]:
                risk = "medium"
            requires_confirmation = True

        # Read/memory/suggestion are always low risk
        if action_type in {"read", "memory", "suggestion"}:
            if not command:
                risk = "low"
                requires_confirmation = False

        return {
            "step": step.get("step", 0),
            "action_type": action_type,
            "risk": risk,
            "requires_confirmation": requires_confirmation,
            "blocked": blocked,
            "blocked_reasons": blocked_reasons,
        }

    def block_if_dangerous(self, plan) -> list[str]:
        """Return a list of reasons the plan should be blocked, or empty if safe."""
        result = self.simulate_plan(plan)
        return result.blocked_reasons

    def _check_blocked(self, command: str) -> list[str]:
        """Check command against blocked patterns."""
        reasons = []
        for pattern in BLOCKED_PATTERNS:
            if pattern.search(command):
                reasons.append(
                    f"Comando bloqueado por padrão destrutivo: {pattern.pattern}"
                )
        return reasons

    def _check_high_risk(self, command: str) -> bool:
        """Check command against high-risk patterns."""
        for pattern in HIGH_RISK_PATTERNS:
            if pattern.search(command):
                return True
        return False

    @staticmethod
    def _suggest_alternative(blocked_reasons: list[str]) -> str:
        if any("rm" in r.lower() for r in blocked_reasons):
            return "Considere mover para uma pasta de quarentena em vez de deletar."
        if any("chmod" in r.lower() or "chown" in r.lower() for r in blocked_reasons):
            return (
                "Altere permissões apenas de arquivos específicos, não recursivamente."
            )
        if any("sudo" in r.lower() for r in blocked_reasons):
            return "Execute sem sudo ou crie uma proposta para o operador aprovar."
        if any("push" in r.lower() for r in blocked_reasons):
            return "Crie um commit local e sugira push manual ao operador."
        return "Revise o plano e crie ações menos destrutivas."
