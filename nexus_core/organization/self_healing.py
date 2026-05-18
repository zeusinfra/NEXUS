from __future__ import annotations

import shlex
from typing import Any

from nexus_core.organization.blackboard import Blackboard, utc_now
from nexus_core.organization.memory import OrganizationalMemoryStore


class SelfHealingEngine:
    """Diagnoses failed executions and prepares safe recovery steps."""

    def __init__(
        self,
        memory: OrganizationalMemoryStore,
        blackboard: Blackboard | None = None,
    ) -> None:
        self.memory = memory
        self.blackboard = blackboard

    def diagnose_failure(
        self,
        *,
        command_id: str,
        proposal_id: str,
        command: str,
        execution: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        evidence = verification.get("evidence") or {}
        stderr_tail = str(evidence.get("stderr_tail") or execution.get("stderr") or "")
        stdout_tail = str(evidence.get("stdout_tail") or execution.get("stdout") or "")
        failure_class = _classify_failure(command, execution, stderr_tail, stdout_tail)
        recovery_steps = _recovery_steps(command, failure_class)
        diagnostic = {
            "command_id": command_id,
            "proposal_id": proposal_id,
            "status": "diagnosed",
            "failure_class": failure_class,
            "summary": execution.get("summary") or verification.get("error", ""),
            "exit_code": execution.get("exit_code"),
            "auto_fix_applied": False,
            "requires_approval": True,
            "recovery_steps": recovery_steps,
            "evidence": {
                "stderr_tail": stderr_tail[-1200:],
                "stdout_tail": stdout_tail[-1200:],
                "verification_status": verification.get("status"),
            },
            "created_at": utc_now(),
        }
        self.memory.record_runtime_event(
            command_id=command_id,
            proposal_id=proposal_id,
            event_type="SELF_HEALING_DIAGNOSTIC",
            payload=diagnostic,
        )
        if self.blackboard:
            self.blackboard.append_self_healing(diagnostic)
            self.blackboard.append_event(
                "ORG_SELF_HEALING_DIAGNOSTIC",
                {
                    "command_id": command_id,
                    "proposal_id": proposal_id,
                    "failure_class": failure_class,
                    "requires_approval": True,
                },
            )
        return diagnostic


def _classify_failure(
    command: str,
    execution: dict[str, Any],
    stderr_tail: str,
    stdout_tail: str,
) -> str:
    text = f"{command}\n{stderr_tail}\n{stdout_tail}".lower()
    summary = str(execution.get("summary") or "").lower()
    exit_code = execution.get("exit_code")
    if "timeout" in summary or "cancelled after timeout" in summary:
        return "timeout"
    if exit_code == 127 or "command not found" in text or "not found" in text:
        return "missing_command"
    if "permission denied" in text:
        return "permission_denied"
    if "cargo check" in text or "cargo build" in text:
        return "rust_build_failure"
    if "cargo test" in text or "pytest" in text or "npm test" in text:
        return "test_failure"
    if "traceback" in text or "exception" in text:
        return "runtime_exception"
    if "failed" in summary:
        return "command_failure"
    return "verification_failure"


def _recovery_steps(command: str, failure_class: str) -> list[dict[str, Any]]:
    executable = _executable(command)
    if failure_class == "rust_build_failure":
        return [
            _step("Inspect compiler error tail", "read_evidence"),
            _step("Inspect Cargo.toml and edited Rust files", "inspect_workspace"),
            _step("Apply minimal patch", "propose_patch"),
            _step("Re-run cargo check", "requires_approval"),
        ]
    if failure_class == "test_failure":
        return [
            _step("Read failing test output", "read_evidence"),
            _step("Locate smallest failing unit", "inspect_workspace"),
            _step("Apply targeted fix", "propose_patch"),
            _step("Re-run the same test command", "requires_approval"),
        ]
    if failure_class == "timeout":
        return [
            _step("Capture timeout and process evidence", "read_evidence"),
            _step("Split command into smaller validation steps", "plan"),
            _step("Re-run with explicit timeout budget", "requires_approval"),
        ]
    if failure_class == "missing_command":
        return [
            _step(
                f"Confirm whether {executable or 'the executable'} is installed",
                "inspect_environment",
            ),
            _step("Suggest install or project-local alternative", "proposal"),
        ]
    return [
        _step("Inspect stdout/stderr evidence", "read_evidence"),
        _step("Identify changed files or missing inputs", "inspect_workspace"),
        _step("Prepare a safe follow-up command or patch", "proposal"),
    ]


def _step(title: str, action_type: str) -> dict[str, str]:
    return {"title": title, "action_type": action_type, "status": "pending"}


def _executable(command: str) -> str:
    try:
        tokens = shlex.split(command or "")
    except ValueError:
        return ""
    return tokens[0] if tokens else ""
