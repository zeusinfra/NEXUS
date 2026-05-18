from __future__ import annotations

import uuid
from typing import Any

from nexus_core.organization.blackboard import Blackboard, utc_now
from nexus_core.organization.memory import OrganizationalMemoryStore


class ActionReplayBuilder:
    """Reconstructs an execution timeline from persisted runtime evidence."""

    def __init__(
        self,
        memory: OrganizationalMemoryStore,
        blackboard: Blackboard | None = None,
    ) -> None:
        self.memory = memory
        self.blackboard = blackboard

    def command_replay(self, command_id: str) -> dict[str, Any]:
        command = self.memory.get_command(command_id)
        if not command:
            raise KeyError(f"Command not found: {command_id}")

        events = list(
            reversed(self.memory.list_runtime_events(command_id=command_id, limit=500))
        )
        verifications = list(
            reversed(self.memory.list_verifications(command_id=command_id, limit=100))
        )
        plans = self.memory.list_execution_plans(command_id=command_id, limit=10)
        plan_steps = []
        for plan in plans:
            plan_steps.extend(
                self.memory.list_execution_steps(plan_id=plan["plan_id"], limit=100)
            )

        timeline = []
        for step in sorted(plan_steps, key=lambda item: item["step_index"]):
            occurred_at = step.get("finished_at") or step.get("updated_at")
            timeline.append(
                {
                    "type": "plan_step",
                    "title": step["title"],
                    "status": step["status"],
                    "action_type": step["action_type"],
                    "created_at": occurred_at or step["created_at"],
                    "planned_at": step["created_at"],
                    "finished_at": step.get("finished_at"),
                    "evidence": step.get("evidence", {}),
                    "error": step.get("error", ""),
                }
            )
        for event in events:
            timeline.append(
                {
                    "type": "runtime_event",
                    "title": _event_title(event),
                    "status": _event_status(event),
                    "event_type": event["event_type"],
                    "stream": event.get("stream"),
                    "created_at": event["created_at"],
                    "payload": _trim_payload(event.get("payload") or {}),
                }
            )
        for verification in verifications:
            timeline.append(
                {
                    "type": "verification",
                    "title": f"Verification {verification['status']}",
                    "status": verification["status"],
                    "target_type": verification["target_type"],
                    "created_at": verification["created_at"],
                    "evidence": _trim_payload(verification.get("evidence") or {}),
                    "error": verification.get("error", ""),
                }
            )
        timeline.sort(key=lambda item: item.get("created_at") or "")

        replay = {
            "replay_id": f"replay_{uuid.uuid4().hex[:12]}",
            "scope": "command",
            "target_id": command_id,
            "headline": _command_headline(command),
            "status": command.get("status"),
            "command": command,
            "plans": plans,
            "timeline": timeline,
            "artifacts": {
                "stdout_path": command.get("stdout_path"),
                "stderr_path": command.get("stderr_path"),
                "evidence_path": command.get("evidence_path"),
            },
            "created_at": utc_now(),
        }
        if self.blackboard:
            self.blackboard.append_event(
                "ORG_ACTION_REPLAY_BUILT",
                {
                    "scope": "command",
                    "target_id": command_id,
                    "status": replay["status"],
                    "events": len(timeline),
                },
            )
        return replay

    def task_replay(self, task_id: str) -> dict[str, Any]:
        commands = self.memory.list_commands(task_id=task_id, limit=200)
        commands = list(reversed(commands))
        command_replays = [
            self.command_replay(command["command_id"]) for command in commands
        ]
        plans = self.memory.list_execution_plans(task_id=task_id, limit=50)
        timeline = []
        for replay in command_replays:
            timeline.extend(replay["timeline"])
        timeline.sort(key=lambda item: item.get("created_at") or "")
        return {
            "replay_id": f"replay_{uuid.uuid4().hex[:12]}",
            "scope": "task",
            "target_id": task_id,
            "headline": f"Replay Task #{task_id}",
            "status": commands[-1]["status"] if commands else "unknown",
            "commands": commands,
            "plans": plans,
            "timeline": timeline,
            "created_at": utc_now(),
        }


def _event_title(event: dict[str, Any]) -> str:
    event_type = event.get("event_type") or "EXECUTION_EVENT"
    payload = event.get("payload") or {}
    if event_type == "COMMAND_STARTED":
        return "Command started"
    if event_type == "COMMAND_FINISHED":
        return f"Command finished: {payload.get('status', 'unknown')}"
    if event_type == "EXECUTION_OUTPUT":
        stream = event.get("stream") or payload.get("stream") or "output"
        return f"{stream} captured"
    if event_type == "SELF_HEALING_DIAGNOSTIC":
        return "Failure diagnosed"
    return event_type.replace("_", " ").title()


def _event_status(event: dict[str, Any]) -> str:
    payload = event.get("payload") or {}
    if "status" in payload:
        return str(payload["status"])
    if event.get("event_type") == "COMMAND_STARTED":
        return "running"
    return "recorded"


def _command_headline(command: dict[str, Any]) -> str:
    command_text = command.get("command") or "command"
    return f"Replay {command.get('command_id')}: {command_text}"


def _trim_payload(payload: dict[str, Any]) -> dict[str, Any]:
    trimmed = dict(payload)
    if "chunk" in trimmed and isinstance(trimmed["chunk"], str):
        trimmed["chunk"] = trimmed["chunk"][-1200:]
    for key in ("stdout", "stderr", "stdout_tail", "stderr_tail"):
        if key in trimmed and isinstance(trimmed[key], str):
            trimmed[key] = trimmed[key][-1200:]
    return trimmed
