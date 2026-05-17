from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "IDLE",
        "current_goal": None,
        "plan": [],
        "health": {"status": "starting", "last_heartbeat": None},
        "agents": {},
        "tasks": {},
        "decisions": [],
        "blockers": [],
        "errors": [],
        "partial_results": [],
        "evidence": [],
        "events": [],
        "updated_at": utc_now(),
    }


@dataclass
class Blackboard:
    path: Path
    memory: Any | None = None

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._state)

    def get(self, key: str, default: Any = None) -> Any:
        return deepcopy(self._state.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value
        self._touch()
        self.save()

    def register_agent(self, agent: dict[str, Any]) -> None:
        agents = self._state.setdefault("agents", {})
        existing = agents.get(agent["role"], {})
        merged = dict(existing)
        merged.update(dict(agent))
        merged.setdefault("agent_id", f"agent_{agent['role']}")
        merged.setdefault("status", "idle")
        merged.setdefault("current_task", None)
        merged.setdefault("confidence", 0.0)
        merged.setdefault("risk_level", agent.get("risk_level", "low"))
        merged.setdefault("last_heartbeat", None)
        merged.setdefault("permissions", list(agent.get("capabilities", [])))
        merged.setdefault("memory_scope", agent.get("department", agent["role"]))
        agents[agent["role"]] = merged
        self._touch()
        self.save()

    def update_agent_status(self, role: str, **changes: Any) -> dict[str, Any]:
        agents = self._state.setdefault("agents", {})
        if role not in agents:
            agents[role] = {
                "agent_id": f"agent_{role}",
                "role": role,
                "status": "idle",
                "current_task": None,
                "confidence": 0.0,
                "risk_level": "low",
                "last_heartbeat": None,
                "permissions": [],
                "memory_scope": role,
            }
        for key, value in changes.items():
            agents[role][key] = value
        agents[role]["last_heartbeat"] = utc_now()
        runtime = dict(agents[role].get("runtime", {}))
        runtime.update(changes)
        runtime["updated_at"] = utc_now()
        agents[role]["runtime"] = runtime
        self._touch()
        self.save()
        return deepcopy(agents[role])

    def create_task(
        self,
        title: str,
        *,
        owner: str,
        goal: str = "",
        priority: int = 3,
        status: str = "queued",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = {
            "id": task_id,
            "title": title,
            "goal": goal or title,
            "owner": owner,
            "priority": priority,
            "status": status,
            "metadata": metadata or {},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self._state.setdefault("tasks", {})[task_id] = task
        if self.memory:
            self.memory.upsert_task(task)
        self._touch()
        self.save()
        return deepcopy(task)

    def update_task(self, task_id: str, **changes: Any) -> dict[str, Any]:
        tasks = self._state.setdefault("tasks", {})
        if task_id not in tasks:
            raise KeyError(f"Task not found: {task_id}")
        tasks[task_id].update(changes)
        tasks[task_id]["updated_at"] = utc_now()
        if self.memory:
            self.memory.upsert_task(tasks[task_id])
        self._touch()
        self.save()
        return deepcopy(tasks[task_id])

    def record_decision(
        self,
        title: str,
        rationale: str,
        *,
        owner: str,
        impact: str = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision = {
            "id": f"dec_{uuid.uuid4().hex[:12]}",
            "title": title,
            "rationale": rationale,
            "owner": owner,
            "impact": impact,
            "metadata": metadata or {},
            "created_at": utc_now(),
        }
        self._state.setdefault("decisions", []).append(decision)
        if self.memory:
            self.memory.record_decision(decision)
        self._touch()
        self.save()
        return deepcopy(decision)

    def append_event(
        self, event_type: str, payload: dict[str, Any] | None = None
    ) -> None:
        events = self._state.setdefault("events", [])
        events.append(
            {"type": event_type, "payload": payload or {}, "created_at": utc_now()}
        )
        self._state["events"] = events[-200:]
        if self.memory:
            self.memory.record_event(event_type, payload or {})
        self._touch()
        self.save()

    def set_current_goal(self, goal: str | None) -> None:
        self._state["current_goal"] = goal
        self._touch()
        self.save()

    def set_plan(self, plan: list[dict[str, Any]]) -> None:
        self._state["plan"] = plan
        self._touch()
        self.save()

    def append_blocker(self, blocker: dict[str, Any]) -> None:
        self._append_limited("blockers", blocker)

    def append_error(self, error: dict[str, Any]) -> None:
        self._append_limited("errors", error)

    def append_partial_result(self, result: dict[str, Any]) -> None:
        self._append_limited("partial_results", result)

    def append_evidence(self, evidence: dict[str, Any]) -> None:
        self._append_limited("evidence", evidence)

    def heartbeat(self, status: str = "online") -> None:
        self._state["health"] = {"status": status, "last_heartbeat": utc_now()}
        self._touch()
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(
            f"{self.path.suffix}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=True, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(self.path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return _empty_state()
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        base = _empty_state()
        base.update(data)
        return base

    def _touch(self) -> None:
        self._state["updated_at"] = utc_now()

    def _append_limited(
        self, key: str, value: dict[str, Any], limit: int = 200
    ) -> None:
        item = dict(value)
        item.setdefault("created_at", utc_now())
        items = self._state.setdefault(key, [])
        items.append(item)
        self._state[key] = items[-limit:]
        self._touch()
        self.save()
