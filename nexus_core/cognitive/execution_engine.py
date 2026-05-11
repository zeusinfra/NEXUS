"""
NEXUS Cognitive Core — Execution Engine.

Policy-gated executor with full SQLite audit trail.
Only executes actions approved by the simulator; high-risk actions
become proposals that require user confirmation.
"""

from __future__ import annotations

import shlex
import subprocess
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from nexus_core.cognitive.cognitive_db import get_connection
from nexus_core.command_policy import validate_command
from nexus_core.observability import get_logger, log_event
from nexus_core.tools import ToolError

logger = get_logger("nexus.cognitive.execution")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class ActionResult:
    id: str
    plan_id: str
    step_index: int
    action_type: str = "read"
    description: str = ""
    status: str = "pending"  # success | failed | blocked | requires_confirmation
    output: str = ""
    error: str = ""
    risk: str = "low"
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CognitiveExecutionEngine:
    """Executes approved cognitive plans with policy enforcement and audit."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    def execute_plan(self, plan, simulation_result) -> list[ActionResult]:
        """Execute all steps of a simulated plan that passed approval."""
        sim_dict = (
            simulation_result.to_dict()
            if hasattr(simulation_result, "to_dict")
            else simulation_result
        )
        plan_dict = plan.to_dict() if hasattr(plan, "to_dict") else plan

        plan_id = plan_dict.get("id", "unknown")
        steps = plan_dict.get("steps", [])
        step_sims = sim_dict.get("step_results", [])
        approved = sim_dict.get("approved_for_auto_execution", False)

        results: list[ActionResult] = []

        for i, step in enumerate(steps):
            step_sim = step_sims[i] if i < len(step_sims) else {}

            # If the whole plan is blocked or the step is blocked, create proposal
            if step_sim.get("blocked"):
                result = self._create_blocked_result(plan_id, i, step, step_sim)
            elif step_sim.get("requires_confirmation") or not approved:
                result = self.propose_action(plan_id, i, step)
            else:
                result = self.execute_step(plan_id, i, step)

            results.append(result)
            self.audit_action(result)

            # Stop on failure
            if result.status == "failed":
                log_event(
                    logger, 30, "plan_execution_halted", plan_id=plan_id, failed_step=i
                )
                break

        return results

    def execute_step(self, plan_id: str, step_index: int, step: dict) -> ActionResult:
        """Execute a single low-risk step."""
        action_type = step.get("action_type", "read")
        description = step.get("description", "")
        command = step.get("command")
        risk = step.get("risk", "low")

        result = ActionResult(
            id=uuid.uuid4().hex[:12],
            plan_id=plan_id,
            step_index=step_index,
            action_type=action_type,
            description=description,
            risk=risk,
            created_at=_now_iso(),
        )

        try:
            if action_type == "command" and command:
                output = self._execute_command(command)
                result.status = "success"
                result.output = output
            elif action_type == "read":
                result.status = "success"
                result.output = f"[READ] {description}"
            elif action_type == "memory":
                result.status = "success"
                result.output = f"[MEMORY] {description}"
            elif action_type == "suggestion":
                result.status = "success"
                result.output = f"[SUGGESTION] {description}"
            elif action_type in {"write", "api"}:
                # These require confirmation in safe mode
                result.status = "requires_confirmation"
                result.output = f"Ação de escrita requer confirmação: {description}"
            else:
                result.status = "success"
                result.output = f"[{action_type.upper()}] {description}"

        except ToolError as e:
            result.status = "blocked"
            result.error = str(e)
            log_event(
                logger,
                30,
                "step_blocked_by_policy",
                plan_id=plan_id,
                step=step_index,
                error=str(e),
            )
        except subprocess.TimeoutExpired:
            result.status = "failed"
            result.error = "Timeout ao executar comando"
        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            log_event(
                logger,
                40,
                "step_execution_error",
                plan_id=plan_id,
                step=step_index,
                error=str(e),
            )

        return result

    def propose_action(self, plan_id: str, step_index: int, step: dict) -> ActionResult:
        """Create a proposal for an action requiring user confirmation."""
        result = ActionResult(
            id=uuid.uuid4().hex[:12],
            plan_id=plan_id,
            step_index=step_index,
            action_type=step.get("action_type", "unknown"),
            description=step.get("description", ""),
            status="requires_confirmation",
            risk=step.get("risk", "medium"),
            output=f"Proposta: {step.get('description', '')}. Comando: {step.get('command', 'N/A')}",
            created_at=_now_iso(),
        )
        log_event(
            logger,
            20,
            "action_proposed",
            action_id=result.id,
            plan_id=plan_id,
            step=step_index,
        )
        return result

    def approve_action(self, action_id: str) -> ActionResult | None:
        """Execute a previously proposed action after user approval."""
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_actions WHERE id = ? AND status = 'requires_confirmation'",
                (action_id,),
            ).fetchone()

        if not row:
            return None

        step = {
            "action_type": row["action_type"],
            "description": row["description"],
            "command": row["command"],
            "risk": row["risk"],
        }

        result = self.execute_step(row["plan_id"], row["step_index"], step)
        result.id = action_id  # Keep original ID

        # Update the existing record
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE cognitive_actions SET status = ?, output = ?, error = ? WHERE id = ?",
                (result.status, result.output, result.error, action_id),
            )

        log_event(
            logger,
            20,
            "action_approved_and_executed",
            action_id=action_id,
            status=result.status,
        )
        return result

    def audit_action(self, result: ActionResult) -> None:
        """Persist action result to the audit trail."""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cognitive_actions "
                "(id, plan_id, step_index, action_type, description, command, status, output, error, risk, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.id,
                    result.plan_id,
                    result.step_index,
                    result.action_type,
                    result.description,
                    None,
                    result.status,
                    result.output,
                    result.error,
                    result.risk,
                    result.created_at,
                ),
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_actions(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ActionResult]:
        query = "SELECT * FROM cognitive_actions WHERE 1=1"
        params: list = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_result(r) for r in rows]

    def get_pending_confirmations(self) -> list[ActionResult]:
        return self.list_actions(status="requires_confirmation")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _execute_command(self, command: str) -> str:
        """Execute a command through the policy gate."""
        tokens = shlex.split(command)
        validate_command(command, tokens, confirmed=False)

        proc = subprocess.run(
            tokens,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if proc.returncode != 0 and proc.stderr:
            log_event(
                logger, 30, "command_stderr", command=command, stderr=proc.stderr[:200]
            )

        return proc.stdout[:2000] if proc.stdout else f"(exit code: {proc.returncode})"

    def _create_blocked_result(
        self,
        plan_id: str,
        step_index: int,
        step: dict,
        sim: dict,
    ) -> ActionResult:
        reasons = sim.get("blocked_reasons", ["Bloqueado por política de segurança"])
        return ActionResult(
            id=uuid.uuid4().hex[:12],
            plan_id=plan_id,
            step_index=step_index,
            action_type=step.get("action_type", "unknown"),
            description=step.get("description", ""),
            status="blocked",
            error="; ".join(reasons),
            risk="critical",
            created_at=_now_iso(),
        )

    @staticmethod
    def _row_to_result(row) -> ActionResult:
        return ActionResult(
            id=row["id"],
            plan_id=row["plan_id"],
            step_index=row["step_index"],
            action_type=row["action_type"],
            description=row["description"],
            status=row["status"],
            output=row["output"],
            error=row["error"],
            risk=row["risk"],
            created_at=row["created_at"],
        )
