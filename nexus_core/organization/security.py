from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nexus_core.command_policy import classify_command
from nexus_core.execution_protocol import (
    ActionState,
    ApprovalScope,
    ExecutionLedger,
    create_command_proposal,
    execute_approved_command,
    read_execution_result,
    request_user_approval,
)
from nexus_core.organization.blackboard import Blackboard, utc_now
from nexus_core.organization.config import NexusOrgConfig
from nexus_core.tools import ToolError


DESTRUCTIVE_HINTS = {
    "rm": "remove files or directories",
    "chmod": "changes file permissions",
    "chown": "changes file ownership",
    "systemctl": "changes or inspects services",
    "apt": "changes system packages",
    "sudo": "requests elevated privileges",
    "dd": "can overwrite block devices",
    "mkfs": "formats filesystems",
}


@dataclass(frozen=True)
class PolicyAssessment:
    command: str
    cwd: str
    executable: str
    category: str
    risk_level: str
    requires_approval: bool
    allowed_to_propose: bool
    sandbox_recommended: bool
    dry_run_recommended: bool
    impact: str
    rollback: str
    warnings: list[str] = field(default_factory=list)


class PolicyEngine:
    """Organizational policy facade around the existing command policy."""

    def assess_command(self, command: str, *, cwd: str) -> PolicyAssessment:
        tokens = shlex.split(command or "")
        if not tokens:
            raise ToolError("command is required.")

        decision = classify_command(tokens)
        exe = Path(tokens[0]).name
        warnings = []
        for token in tokens:
            name = Path(token).name
            if name in DESTRUCTIVE_HINTS:
                warnings.append(f"{name}: {DESTRUCTIVE_HINTS[name]}")

        risk_level = "LOW"
        if decision.category in {"write", "exec"}:
            risk_level = "MEDIUM"
        if warnings or exe in {"sudo", "rm", "dd", "mkfs", "apt", "systemctl"}:
            risk_level = "HIGH"

        return PolicyAssessment(
            command=command,
            cwd=str(Path(cwd).expanduser().resolve()),
            executable=exe,
            category=decision.category,
            risk_level=risk_level,
            requires_approval=True,
            allowed_to_propose=True,
            sandbox_recommended=risk_level != "LOW",
            dry_run_recommended=decision.category != "read" or risk_level == "HIGH",
            impact=self._impact_for(decision.category, warnings),
            rollback=self._rollback_for(decision.category, exe),
            warnings=warnings,
        )

    def _impact_for(self, category: str, warnings: list[str]) -> str:
        if warnings:
            return "May alter files, services, packages, permissions, or privileged system state."
        if category == "read":
            return "Read-only inspection; no filesystem or service changes expected."
        if category == "write":
            return "May write to the filesystem or modify project state."
        return "Command execution requires argument review before approval."

    def _rollback_for(self, category: str, exe: str) -> str:
        if category == "read":
            return "No rollback expected for read-only command."
        if exe == "systemctl":
            return "Record previous service state; revert with the inverse systemctl action if safe."
        if exe in {"apt", "pip", "pip3", "npm", "cargo"}:
            return "Record package/action output; rollback depends on package manager state."
        return "Prefer dry-run or backup first; rollback must be defined by the approving operator."


class ApprovalQueue:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        items = self._load()
        if status:
            return [item for item in items if item.get("status") == status]
        return items

    def upsert(self, item: dict[str, Any]) -> dict[str, Any]:
        items = self._load()
        proposal_id = item["proposal_id"]
        replaced = False
        for idx, current in enumerate(items):
            if current.get("proposal_id") == proposal_id:
                merged = dict(current)
                merged.update(item)
                merged["updated_at"] = utc_now()
                items[idx] = merged
                item = merged
                replaced = True
                break
        if not replaced:
            item = dict(item)
            item.setdefault("created_at", utc_now())
            item["updated_at"] = utc_now()
            items.append(item)
        self._save(items)
        return item

    def get(self, proposal_id: str) -> dict[str, Any]:
        for item in self._load():
            if item.get("proposal_id") == proposal_id:
                return item
        raise KeyError(f"Approval item not found: {proposal_id}")

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, items: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(
            f"{self.path.suffix}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=True, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(self.path)


class PermissionManager:
    """Creates auditable proposals and approvals without bypassing the ledger."""

    def __init__(
        self,
        config: NexusOrgConfig,
        blackboard: Blackboard,
        *,
        policy: PolicyEngine | None = None,
        ledger: ExecutionLedger | None = None,
        queue: ApprovalQueue | None = None,
    ) -> None:
        self.config = config
        self.blackboard = blackboard
        self.policy = policy or PolicyEngine()
        self.ledger = ledger or ExecutionLedger()
        self.queue = queue or ApprovalQueue(
            config.approvals_dir / "pending_commands.json"
        )

    def propose_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        reason: str = "",
        requested_by: str = "organization",
    ) -> dict[str, Any]:
        cwd = str(Path(cwd or self.config.project_root).expanduser().resolve())
        assessment = self.policy.assess_command(command, cwd=cwd)
        proposal = create_command_proposal(
            command,
            cwd=cwd,
            reason=reason or assessment.impact,
            ledger=self.ledger,
        )
        queue_status = (
            "blocked"
            if proposal["status"] == ActionState.BLOCKED.value
            else "pending_approval"
        )
        item = self.queue.upsert(
            {
                "proposal_id": proposal["proposal_id"],
                "approval_id": proposal.get("approval_id"),
                "command": command,
                "cwd": cwd,
                "status": queue_status,
                "ledger_status": proposal["status"],
                "requested_by": requested_by,
                "reason": reason,
                "assessment": asdict(assessment),
                "risk_level": proposal.get("risk_level", assessment.risk_level),
                "summary": proposal.get("summary", ""),
            }
        )
        self.blackboard.append_event(
            "ORG_COMMAND_PROPOSED",
            {
                "proposal_id": proposal["proposal_id"],
                "status": queue_status,
                "risk_level": item["risk_level"],
                "command": command,
            },
        )
        return item

    def approve_command(
        self,
        proposal_id: str,
        *,
        approved_by: str,
        approval_scope: ApprovalScope = ApprovalScope.ONCE,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        item = self.queue.get(proposal_id)
        approval = request_user_approval(
            proposal_id,
            approved_by=approved_by,
            approval_scope=approval_scope,
            ttl_seconds=ttl_seconds,
            ledger=self.ledger,
        )
        updated = self.queue.upsert(
            {
                **item,
                "approval_id": approval["approval_id"],
                "status": "approved",
                "ledger_status": approval["status"],
                "approved_by": approved_by,
                "expires_at": approval.get("expires_at"),
            }
        )
        self.blackboard.append_event(
            "ORG_COMMAND_APPROVED",
            {
                "proposal_id": proposal_id,
                "approval_id": approval["approval_id"],
                "approved_by": approved_by,
            },
        )
        return updated

    async def execute_command(
        self,
        proposal_id: str,
        *,
        timeout_s: int = 30,
    ) -> dict[str, Any]:
        item = self.queue.get(proposal_id)
        approval_id = item.get("approval_id")
        if not approval_id:
            raise ToolError("Command is not approved; approval_id is missing.")
        result = await execute_approved_command(
            proposal_id,
            approval_id,
            timeout_s=timeout_s,
            ledger=self.ledger,
        )
        status = (
            "executed" if result["status"] == ActionState.SUCCEEDED.value else "failed"
        )
        updated = self.queue.upsert(
            {
                **item,
                "status": status,
                "ledger_status": result["status"],
                "exit_code": result.get("exit_code"),
                "summary": result.get("summary", ""),
            }
        )
        self.blackboard.append_event(
            "ORG_COMMAND_EXECUTION_FINISHED",
            {
                "proposal_id": proposal_id,
                "status": result["status"],
                "exit_code": result.get("exit_code"),
            },
        )
        return {**updated, "execution": read_execution_result(proposal_id)}

    def execute_command_sync(
        self, proposal_id: str, *, timeout_s: int = 30
    ) -> dict[str, Any]:
        return asyncio.run(self.execute_command(proposal_id, timeout_s=timeout_s))
