from __future__ import annotations

import uuid
from typing import Any

from nexus_core.organization.blackboard import Blackboard, utc_now
from nexus_core.organization.memory import OrganizationalMemoryStore


COMMAND_EXECUTION_TEMPLATE = [
    ("Validate approval", "approval"),
    ("Check resource budget", "resource_budget"),
    ("Run approved command", "command_execution"),
    ("Verify execution evidence", "verification"),
    ("Persist action replay", "replay"),
]


class StructuredExecutionPlanner:
    """Creates auditable plan -> steps -> execution records."""

    def __init__(
        self,
        memory: OrganizationalMemoryStore,
        blackboard: Blackboard | None = None,
    ) -> None:
        self.memory = memory
        self.blackboard = blackboard

    def create_command_plan(
        self,
        *,
        command_id: str,
        proposal_id: str,
        command: str,
        cwd: str,
        task_id: str | None = None,
        agent: str = "runtime",
        timeout_s: int = 30,
        workspace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        tags = list((workspace_context or {}).get("tags") or [])
        plan = {
            "plan_id": plan_id,
            "task_id": task_id,
            "command_id": command_id,
            "proposal_id": proposal_id,
            "title": _title_for_command(command),
            "objective": command,
            "status": "running",
            "metadata": {
                "agent": agent,
                "cwd": cwd,
                "timeout_s": timeout_s,
                "workspace_tags": tags[:12],
            },
            "created_at": utc_now(),
        }
        plan = self.memory.record_execution_plan(plan)
        steps = []
        for index, (title, action_type) in enumerate(
            COMMAND_EXECUTION_TEMPLATE, start=1
        ):
            step = self.memory.record_execution_step(
                {
                    "step_id": f"step_{uuid.uuid4().hex[:12]}",
                    "plan_id": plan_id,
                    "step_index": index,
                    "title": title,
                    "action_type": action_type,
                    "status": "pending",
                    "command_id": command_id,
                    "evidence": {},
                    "created_at": utc_now(),
                }
            )
            steps.append(step)
        payload = {**plan, "steps": steps}
        if self.blackboard:
            self.blackboard.upsert_execution_plan(payload)
            self.blackboard.append_event(
                "ORG_EXECUTION_PLAN_CREATED",
                {
                    "plan_id": plan_id,
                    "command_id": command_id,
                    "proposal_id": proposal_id,
                    "steps": len(steps),
                },
            )
        return payload

    def step_by_action(self, plan: dict[str, Any], action_type: str) -> dict[str, Any]:
        for step in plan.get("steps", []):
            if step.get("action_type") == action_type:
                return step
        raise KeyError(f"Execution step not found for action: {action_type}")

    def mark_step(
        self,
        plan: dict[str, Any],
        action_type: str,
        status: str,
        *,
        evidence: dict[str, Any] | None = None,
        error: str = "",
        finished: bool = False,
    ) -> dict[str, Any]:
        step = self.step_by_action(plan, action_type)
        updated = self.memory.update_execution_step(
            step["step_id"],
            status=status,
            evidence=evidence,
            error=error,
            finished=finished,
        )
        for index, current in enumerate(plan.get("steps", [])):
            if current.get("step_id") == updated["step_id"]:
                plan["steps"][index] = updated
                break
        if self.blackboard:
            self.blackboard.upsert_execution_plan(plan)
        return updated

    def finish_plan(
        self,
        plan: dict[str, Any],
        *,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_metadata = dict(plan.get("metadata") or {})
        if metadata:
            merged_metadata.update(metadata)
        updated = self.memory.update_execution_plan(
            plan["plan_id"],
            status=status,
            metadata=merged_metadata,
            finished=True,
        )
        plan.update(updated)
        if self.blackboard:
            self.blackboard.upsert_execution_plan(plan)
            self.blackboard.append_event(
                "ORG_EXECUTION_PLAN_FINISHED",
                {
                    "plan_id": plan["plan_id"],
                    "command_id": plan.get("command_id"),
                    "status": status,
                },
            )
        return {**updated, "steps": list(plan.get("steps", []))}


def _title_for_command(command: str) -> str:
    tokens = (command or "").strip().split()
    if not tokens:
        return "Execute approved command"
    head = " ".join(tokens[:3])
    return f"Execute {head}"
