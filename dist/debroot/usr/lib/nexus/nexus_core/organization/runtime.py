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
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.organization.security import ApprovalQueue
from nexus_core.organization.verification import VerificationEngine
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
        self.memory.record_command(
            {
                "command_id": command_id,
                "agent_id": agent,
                "task_id": item.get("task_id"),
                "proposal_id": proposal_id,
                "command": item.get("command", ""),
                "cwd": item.get("cwd", ""),
                "status": "running",
                "risk_level": item.get("risk_level", "LOW"),
                "metadata": {"approval_id": approval_id},
            }
        )
        self.memory.record_runtime_event(
            command_id=command_id,
            proposal_id=proposal_id,
            event_type="COMMAND_STARTED",
            payload={
                "agent": agent,
                "command": item.get("command"),
                "cwd": item.get("cwd"),
                "risk_level": item.get("risk_level"),
            },
        )
        self.blackboard.append_event(
            "ORG_RUNTIME_COMMAND_STARTED",
            {"command_id": command_id, "proposal_id": proposal_id, "agent": agent},
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

        result = await execute_approved_command(
            proposal_id,
            approval_id,
            timeout_s=timeout_s,
            on_event=on_event,
            ledger=self.ledger,
        )
        result_with_output = read_execution_result(proposal_id)
        verification = self.verifier.verify_execution(
            result_with_output, command_id=command_id
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
                "command": item.get("command", ""),
                "cwd": item.get("cwd", ""),
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
                    "ledger_status": result.get("status"),
                    "verification_status": verification.get("status"),
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
        }
