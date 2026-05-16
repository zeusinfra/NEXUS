from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator

from nexus_core.organization.blackboard import utc_now


@dataclass
class OrganizationalMemoryStore:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 3,
                    status TEXT NOT NULL DEFAULT 'queued',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_decisions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    impact TEXT NOT NULL DEFAULT 'medium',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_summaries (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_runtime_events (
                    id TEXT PRIMARY KEY,
                    command_id TEXT NOT NULL,
                    proposal_id TEXT,
                    event_type TEXT NOT NULL,
                    stream TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_verifications (
                    id TEXT PRIMARY KEY,
                    command_id TEXT,
                    target_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_observations (
                    id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    active_window TEXT,
                    system_json TEXT NOT NULL DEFAULT '{}',
                    processes_json TEXT NOT NULL DEFAULT '[]',
                    triggers_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_agent_ticks (
                    id TEXT PRIMARY KEY,
                    agent_role TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_tasks_status ON org_tasks(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_tasks_owner ON org_tasks(owner)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_events_type ON org_events(event_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_events_created ON org_events(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_summaries_scope ON org_summaries(scope)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_runtime_command ON org_runtime_events(command_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_runtime_created ON org_runtime_events(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_verifications_command ON org_verifications(command_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_observations_created ON org_observations(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_agent_ticks_role ON org_agent_ticks(agent_role)"
            )

    def upsert_task(self, task: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_tasks (
                    id, title, goal, owner, priority, status, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    goal = excluded.goal,
                    owner = excluded.owner,
                    priority = excluded.priority,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    task["id"],
                    task["title"],
                    task.get("goal", ""),
                    task["owner"],
                    int(task.get("priority", 3)),
                    task.get("status", "queued"),
                    _json(task.get("metadata", {})),
                    task.get("created_at") or utc_now(),
                    task.get("updated_at") or utc_now(),
                ),
            )

    def record_decision(self, decision: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO org_decisions (
                    id, title, rationale, owner, impact, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision["id"],
                    decision["title"],
                    decision["rationale"],
                    decision["owner"],
                    decision.get("impact", "medium"),
                    _json(decision.get("metadata", {})),
                    decision.get("created_at") or utc_now(),
                ),
            )

    def record_event(
        self, event_type: str, payload: dict[str, Any] | None = None
    ) -> str:
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_events (id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, event_type, _json(payload or {}), utc_now()),
            )
        return event_id

    def create_summary(
        self,
        scope: str = "recent",
        *,
        limit: int = 20,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if summary is None:
            summary = self.summarize_recent(limit=limit)
        item = {
            "id": f"sum_{uuid.uuid4().hex[:12]}",
            "scope": scope,
            "summary": summary,
            "metadata": metadata or {"limit": limit},
            "created_at": utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_summaries (id, scope, summary, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["scope"],
                    item["summary"],
                    _json(item["metadata"]),
                    item["created_at"],
                ),
            )
        return item

    def record_runtime_event(
        self,
        *,
        command_id: str,
        event_type: str,
        proposal_id: str | None = None,
        stream: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        event_id = f"rte_{uuid.uuid4().hex[:12]}"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_runtime_events (
                    id, command_id, proposal_id, event_type, stream, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    command_id,
                    proposal_id,
                    event_type,
                    stream,
                    _json(payload or {}),
                    utc_now(),
                ),
            )
        return event_id

    def record_verification(
        self,
        *,
        target_type: str,
        target: str,
        status: str,
        command_id: str | None = None,
        evidence: dict[str, Any] | None = None,
        error: str = "",
    ) -> dict[str, Any]:
        item = {
            "id": f"ver_{uuid.uuid4().hex[:12]}",
            "command_id": command_id,
            "target_type": target_type,
            "target": target,
            "status": status,
            "evidence": evidence or {},
            "error": error,
            "created_at": utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_verifications (
                    id, command_id, target_type, target, status, evidence_json, error, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    command_id,
                    target_type,
                    target,
                    status,
                    _json(item["evidence"]),
                    error,
                    item["created_at"],
                ),
            )
        return item

    def record_observation(self, observation: dict[str, Any]) -> dict[str, Any]:
        item = dict(observation)
        item.setdefault("id", f"obs_{uuid.uuid4().hex[:12]}")
        item.setdefault("created_at", utc_now())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_observations (
                    id, mode, confidence, active_window, system_json, processes_json,
                    triggers_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["mode"],
                    float(item.get("confidence", 0.0)),
                    item.get("active_window"),
                    _json(item.get("system", {})),
                    _json(item.get("processes", [])),
                    _json(item.get("triggers", [])),
                    item["created_at"],
                ),
            )
        return item

    def record_agent_tick(
        self,
        *,
        agent_role: str,
        mode: str,
        status: str,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "id": f"agt_{uuid.uuid4().hex[:12]}",
            "agent_role": agent_role,
            "mode": mode,
            "status": status,
            "summary": summary,
            "metadata": metadata or {},
            "created_at": utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_agent_ticks (
                    id, agent_role, mode, status, summary, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    agent_role,
                    mode,
                    status,
                    summary,
                    _json(item["metadata"]),
                    item["created_at"],
                ),
            )
        return item

    def summarize_recent(self, *, limit: int = 20) -> str:
        tasks = self.list_tasks(limit=limit)
        decisions = self.list_decisions(limit=limit)
        events = self.list_events(limit=limit)
        open_tasks = [
            task for task in tasks if task["status"] not in {"done", "cancelled"}
        ]
        lines = [
            f"Organizational memory snapshot: {len(open_tasks)} open task(s), "
            f"{len(decisions)} recent decision(s), {len(events)} recent event(s).",
        ]
        if open_tasks:
            lines.append(
                "Top tasks: "
                + "; ".join(
                    f"{task['owner']}:{task['title']}" for task in open_tasks[:5]
                )
            )
        if decisions:
            lines.append(
                "Recent decisions: "
                + "; ".join(decision["title"] for decision in decisions[:5])
            )
        if events:
            lines.append(
                "Recent events: "
                + "; ".join(event["event_type"] for event in events[:8])
            )
        return "\n".join(lines)

    def list_tasks(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_tasks"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [self._task_from_row(row) for row in self._fetch(query, params)]

    def list_decisions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._fetch(
            "SELECT * FROM org_decisions ORDER BY created_at DESC LIMIT ?", [limit]
        )
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "rationale": row["rationale"],
                "owner": row["owner"],
                "impact": row["impact"],
                "metadata": _loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_events(
        self, *, event_type: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_events"
        params: list[Any] = []
        if event_type:
            query += " WHERE event_type = ?"
            params.append(event_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "payload": _loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_summaries(
        self, *, scope: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_summaries"
        params: list[Any] = []
        if scope:
            query += " WHERE scope = ?"
            params.append(scope)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "id": row["id"],
                "scope": row["scope"],
                "summary": row["summary"],
                "metadata": _loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_runtime_events(
        self, *, command_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_runtime_events"
        params: list[Any] = []
        if command_id:
            query += " WHERE command_id = ?"
            params.append(command_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "id": row["id"],
                "command_id": row["command_id"],
                "proposal_id": row["proposal_id"],
                "event_type": row["event_type"],
                "stream": row["stream"],
                "payload": _loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_verifications(
        self, *, command_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_verifications"
        params: list[Any] = []
        if command_id:
            query += " WHERE command_id = ?"
            params.append(command_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "id": row["id"],
                "command_id": row["command_id"],
                "target_type": row["target_type"],
                "target": row["target"],
                "status": row["status"],
                "evidence": _loads(row["evidence_json"]),
                "error": row["error"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_observations(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._fetch(
            "SELECT * FROM org_observations ORDER BY created_at DESC LIMIT ?",
            [limit],
        )
        return [
            {
                "id": row["id"],
                "mode": row["mode"],
                "confidence": row["confidence"],
                "active_window": row["active_window"],
                "system": _loads(row["system_json"]),
                "processes": _loads(row["processes_json"]),
                "triggers": _loads(row["triggers_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_agent_ticks(
        self, *, agent_role: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_agent_ticks"
        params: list[Any] = []
        if agent_role:
            query += " WHERE agent_role = ?"
            params.append(agent_role)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "id": row["id"],
                "agent_role": row["agent_role"],
                "mode": row["mode"],
                "status": row["status"],
                "summary": row["summary"],
                "metadata": _loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def counts(self) -> dict[str, int]:
        with self.connect() as conn:
            return {
                "tasks": conn.execute("SELECT COUNT(*) FROM org_tasks").fetchone()[0],
                "decisions": conn.execute(
                    "SELECT COUNT(*) FROM org_decisions"
                ).fetchone()[0],
                "events": conn.execute("SELECT COUNT(*) FROM org_events").fetchone()[0],
                "summaries": conn.execute(
                    "SELECT COUNT(*) FROM org_summaries"
                ).fetchone()[0],
                "runtime_events": conn.execute(
                    "SELECT COUNT(*) FROM org_runtime_events"
                ).fetchone()[0],
                "verifications": conn.execute(
                    "SELECT COUNT(*) FROM org_verifications"
                ).fetchone()[0],
                "observations": conn.execute(
                    "SELECT COUNT(*) FROM org_observations"
                ).fetchone()[0],
                "agent_ticks": conn.execute(
                    "SELECT COUNT(*) FROM org_agent_ticks"
                ).fetchone()[0],
            }

    def _fetch(self, query: str, params: list[Any]) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(query, params).fetchall())

    def _task_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "goal": row["goal"],
            "owner": row["owner"],
            "priority": row["priority"],
            "status": row["status"],
            "metadata": _loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _loads(value: str) -> Any:
    return json.loads(value or "{}")
