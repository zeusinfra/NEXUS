from __future__ import annotations

import time
import uuid
from typing import Any

from nexus_core.execution_protocol import (
    ActionState,
    ExecutionLedger,
    execute_approved_command,
    read_execution_result,
)
from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.execution_plans import StructuredExecutionPlanner
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.organization.replay import ActionReplayBuilder
from nexus_core.organization.resource_budget import ResourceBudgetGovernor
from nexus_core.organization.security import ApprovalQueue
from nexus_core.organization.self_healing import SelfHealingEngine
from nexus_core.organization.verification import VerificationEngine
from nexus_core.organization.workspace_context import WorkspaceMemory
from nexus_core.sentry_observability import add_breadcrumb, capture_message
from nexus_core.tools import ToolError


class RuntimeEngine:
    """Real execution runtime with auditable command ids and evidence."""

    def __init__(
        self,
        config: NexusOrgConfig,
        blackboard: Blackboard,
        memory: OrganizationalMemoryStore,
        *,
        ledger: ExecutionLedger | None = None,
        queue: ApprovalQueue | None = None,
        verifier: VerificationEngine | None = None,
    ) -> None:
        self.config = config
        self.blackboard = blackboard
        self.memory = memory
        self.ledger = ledger or ExecutionLedger()
        self.queue = queue or ApprovalQueue(
            config.approvals_dir / "pending_commands.json"
        )
        self.verifier = verifier or VerificationEngine(memory)
        self.planner = StructuredExecutionPlanner(memory, blackboard)
        self.replay_builder = ActionReplayBuilder(memory, blackboard)
        self.resource_governor = ResourceBudgetGovernor()
        self.self_healing = SelfHealingEngine(memory, blackboard)
        self.workspace_memory = WorkspaceMemory(config.project_root)
        self._active_executions = 0

    async def execute_approved(
        self,
        proposal_id: str,
        *,
        agent: str = "runtime",
        timeout_s: int = 30,
    ) -> dict[str, Any]:
        item = self.queue.get(proposal_id)
        approval_id = item.get("approval_id")
        if not approval_id:
            raise ToolError("Command is not approved; approval_id is missing.")

        command_id = f"cmd_{uuid.uuid4().hex[:12]}"
        started = time.perf_counter()
        command = item.get("command", "")
        cwd = item.get("cwd", "")
        workspace_context = self.blackboard.get("workspace_context", {})
        if not workspace_context:
            workspace_context = self.workspace_memory.analyze()
            self.blackboard.set_workspace_context(workspace_context)
        budget = self.resource_governor.assess(
            active_executions=self._active_executions,
            requested_timeout_s=timeout_s,
        )
        self.blackboard.set_resource_budget(budget)
        timeout_s = int(budget["effective_timeout_s"])
        plan = self.planner.create_command_plan(
            command_id=command_id,
            proposal_id=proposal_id,
            command=command,
            cwd=cwd,
            task_id=item.get("task_id"),
            agent=agent,
            timeout_s=timeout_s,
            workspace_context=workspace_context,
        )
        self.planner.mark_step(
            plan,
            "approval",
            "passed",
            evidence={"approval_id": approval_id, "proposal_id": proposal_id},
            finished=True,
        )
        resource_status = "passed" if budget["allowed"] else "failed"
        self.planner.mark_step(
            plan,
            "resource_budget",
            resource_status,
            evidence=budget,
            error="; ".join(budget["reasons"]),
            finished=True,
        )
        self.memory.record_command(
            {
                "command_id": command_id,
                "agent_id": agent,
                "task_id": item.get("task_id"),
                "proposal_id": proposal_id,
                "command": command,
                "cwd": cwd,
                "status": "running",
                "risk_level": item.get("risk_level", "LOW"),
                "metadata": {
                    "approval_id": approval_id,
                    "plan_id": plan["plan_id"],
                    "resource_budget": budget,
                },
            }
        )
        self.memory.record_runtime_event(
            command_id=command_id,
            proposal_id=proposal_id,
            event_type="COMMAND_STARTED",
            payload={
                "agent": agent,
                "command": command,
                "cwd": cwd,
                "risk_level": item.get("risk_level"),
                "plan_id": plan["plan_id"],
                "resource_mode": budget["mode"],
            },
        )
        self.blackboard.append_event(
            "ORG_RUNTIME_COMMAND_STARTED",
            {
                "command_id": command_id,
                "proposal_id": proposal_id,
                "agent": agent,
                "plan_id": plan["plan_id"],
            },
        )
        add_breadcrumb(
            "command executed",
            category="runtime",
            data={
                "agent_id": agent,
                "command_id": command_id,
                "proposal_id": proposal_id,
                "risk_level": item.get("risk_level"),
            },
        )

        async def on_event(payload: dict[str, Any]) -> None:
            event_type = (
                payload.get("type")
                or payload.get("event")
                or payload.get("status")
                or "EXECUTION_EVENT"
            )
            self.memory.record_runtime_event(
                command_id=command_id,
                proposal_id=proposal_id,
                event_type=str(event_type),
                stream=payload.get("stream"),
                payload=payload,
            )

        if budget["allowed"]:
            self.planner.mark_step(
                plan,
                "command_execution",
                "running",
                evidence={"timeout_s": timeout_s},
            )
            try:
                self._active_executions += 1
                result = await execute_approved_command(
                    proposal_id,
                    approval_id,
                    timeout_s=timeout_s,
                    on_event=on_event,
                    ledger=self.ledger,
                )
                result_with_output = read_execution_result(proposal_id)
            except ToolError as exc:
                result = {
                    "proposal_id": proposal_id,
                    "approval_id": approval_id,
                    "command": command,
                    "cwd": cwd,
                    "status": ActionState.FAILED.value,
                    "exit_code": None,
                    "summary": str(exc),
                    "verified_by_executor": True,
                }
                result_with_output = dict(result)
            finally:
                self._active_executions = max(0, self._active_executions - 1)
            execution_ok = result.get("status") == ActionState.SUCCEEDED.value
            self.planner.mark_step(
                plan,
                "command_execution",
                "passed" if execution_ok else "failed",
                evidence={
                    "status": result.get("status"),
                    "exit_code": result.get("exit_code"),
                    "summary": result.get("summary", ""),
                },
                error="" if execution_ok else result.get("summary", ""),
                finished=True,
            )
        else:
            summary = "Resource budget denied execution: " + "; ".join(
                budget["reasons"]
            )
            result = {
                "proposal_id": proposal_id,
                "approval_id": approval_id,
                "command": command,
                "cwd": cwd,
                "status": ActionState.BLOCKED.value,
                "exit_code": None,
                "summary": summary,
                "verified_by_executor": True,
            }
            result_with_output = dict(result)
            self.planner.mark_step(
                plan,
                "command_execution",
                "blocked",
                evidence={"status": ActionState.BLOCKED.value},
                error=summary,
                finished=True,
            )

        self.planner.mark_step(
            plan,
            "verification",
            "running",
            evidence={"command_id": command_id},
        )
        verification = self.verifier.verify_execution(
            result_with_output, command_id=command_id
        )
        self.planner.mark_step(
            plan,
            "verification",
            "passed" if verification.get("status") == "passed" else "failed",
            evidence=verification,
            error=verification.get("error", ""),
            finished=True,
        )
        duration_ms = round((time.perf_counter() - started) * 1000)
        final_status = (
            "executed"
            if result.get("status") == ActionState.SUCCEEDED.value
            and verification.get("status") == "passed"
            else "failed"
        )
        self.memory.record_command(
            {
                "command_id": command_id,
                "agent_id": agent,
                "task_id": item.get("task_id"),
                "proposal_id": proposal_id,
                "command": command,
                "cwd": cwd,
                "status": final_status,
                "pid": result_with_output.get("pid") or result.get("pid"),
                "exit_code": result.get("exit_code"),
                "duration_ms": duration_ms,
                "stdout_path": result_with_output.get("stdout_path"),
                "stderr_path": result_with_output.get("stderr_path"),
                "evidence_path": result_with_output.get("evidence_path"),
                "risk_level": item.get("risk_level", "LOW"),
                "finished_at": verification.get("created_at"),
                "metadata": {
                    "approval_id": approval_id,
                    "plan_id": plan["plan_id"],
                    "ledger_status": result.get("status"),
                    "verification_status": verification.get("status"),
                    "resource_budget": budget,
                },
            }
        )
        updated = self.queue.upsert(
            {
                **item,
                "command_id": command_id,
                "status": final_status,
                "ledger_status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "summary": result.get("summary", ""),
                "duration_ms": duration_ms,
                "verification_status": verification.get("status"),
            }
        )
        self.memory.record_approval(updated)
        healing = None
        if final_status == "failed":
            healing = self.self_healing.diagnose_failure(
                command_id=command_id,
                proposal_id=proposal_id,
                command=command,
                execution=result_with_output,
                verification=verification,
            )
        self.memory.record_runtime_event(
            command_id=command_id,
            proposal_id=proposal_id,
            event_type="COMMAND_FINISHED",
            payload={
                "status": final_status,
                "ledger_status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "duration_ms": duration_ms,
                "verification_status": verification.get("status"),
                "plan_id": plan["plan_id"],
            },
        )
        self.blackboard.append_event(
            "ORG_RUNTIME_COMMAND_FINISHED",
            {
                "command_id": command_id,
                "proposal_id": proposal_id,
                "status": final_status,
                "verification_status": verification.get("status"),
            },
        )
        if final_status == "failed":
            self.memory.record_incident(
                severity="error",
                module="runtime",
                message=result.get("summary") or "Command execution failed",
                agent_id=agent,
                task_id=item.get("task_id"),
                command_id=command_id,
                risk_level=item.get("risk_level"),
                metadata={
                    "proposal_id": proposal_id,
                    "exit_code": result.get("exit_code"),
                    "verification_status": verification.get("status"),
                },
            )
            capture_message(
                "Command execution failed",
                module="runtime",
                level="error",
                tags={
                    "agent_id": agent,
                    "task_id": item.get("task_id"),
                    "command_id": command_id,
                    "risk_level": item.get("risk_level"),
                    "execution_status": final_status,
                },
                context={
                    "proposal_id": proposal_id,
                    "exit_code": result.get("exit_code"),
                    "verification": verification,
                },
            )
        self.planner.mark_step(
            plan,
            "replay",
            "passed",
            evidence={"command_id": command_id, "status": final_status},
            finished=True,
        )
        execution_plan = self.planner.finish_plan(
            plan,
            status="completed" if final_status == "executed" else "failed",
            metadata={
                "duration_ms": duration_ms,
                "final_status": final_status,
                "verification_status": verification.get("status"),
            },
        )
        replay = self.replay_builder.command_replay(command_id)
        add_breadcrumb(
            "verification completed",
            category="runtime",
            data={
                "agent_id": agent,
                "command_id": command_id,
                "status": final_status,
                "verification_status": verification.get("status"),
            },
        )
        return {
            **updated,
            "execution": result_with_output,
            "verification": verification,
            "runtime_events": self.memory.list_runtime_events(command_id=command_id),
            "execution_plan": execution_plan,
            "resource_budget": budget,
            "workspace_context": workspace_context,
            "self_healing": healing,
            "replay": replay,
        }
