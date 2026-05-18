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
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA busy_timeout=5000")
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_agents (
                    agent_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'idle',
                    current_task TEXT,
                    confidence REAL NOT NULL DEFAULT 0,
                    risk_level TEXT NOT NULL DEFAULT 'low',
                    permissions_json TEXT NOT NULL DEFAULT '[]',
                    memory_scope TEXT NOT NULL DEFAULT '',
                    last_heartbeat TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_commands (
                    command_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    task_id TEXT,
                    proposal_id TEXT,
                    command TEXT NOT NULL,
                    cwd TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pid INTEGER,
                    exit_code INTEGER,
                    duration_ms INTEGER,
                    stdout_path TEXT,
                    stderr_path TEXT,
                    evidence_path TEXT,
                    risk_level TEXT NOT NULL DEFAULT 'LOW',
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_incidents (
                    id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL,
                    agent_id TEXT,
                    task_id TEXT,
                    command_id TEXT,
                    risk_level TEXT,
                    sentry_event_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_approvals (
                    proposal_id TEXT PRIMARY KEY,
                    approval_id TEXT,
                    command TEXT NOT NULL,
                    cwd TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    impact TEXT NOT NULL DEFAULT '',
                    rollback TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_memory_entries (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_execution_plans (
                    plan_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    command_id TEXT,
                    proposal_id TEXT,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'planned',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_execution_steps (
                    step_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    command_id TEXT,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_agents_role ON org_agents(role)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_commands_status ON org_commands(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_commands_task ON org_commands(task_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_incidents_command ON org_incidents(command_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_approvals_status ON org_approvals(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_memory_scope ON org_memory_entries(scope)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_execution_plans_task ON org_execution_plans(task_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_execution_plans_command ON org_execution_plans(command_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_execution_plans_status ON org_execution_plans(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_execution_steps_plan ON org_execution_steps(plan_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_execution_steps_command ON org_execution_steps(command_id)"
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

    def record_agent_state(
        self,
        *,
        agent_id: str,
        role: str,
        status: str,
        current_task: str | None = None,
        confidence: float = 0.0,
        risk_level: str = "low",
        permissions: list[str] | None = None,
        memory_scope: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "agent_id": agent_id,
            "role": role,
            "status": status,
            "current_task": current_task,
            "confidence": float(confidence),
            "risk_level": risk_level,
            "permissions": permissions or [],
            "memory_scope": memory_scope,
            "last_heartbeat": utc_now(),
            "metadata": metadata or {},
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_agents (
                    agent_id, role, status, current_task, confidence, risk_level,
                    permissions_json, memory_scope, last_heartbeat, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    role = excluded.role,
                    status = excluded.status,
                    current_task = excluded.current_task,
                    confidence = excluded.confidence,
                    risk_level = excluded.risk_level,
                    permissions_json = excluded.permissions_json,
                    memory_scope = excluded.memory_scope,
                    last_heartbeat = excluded.last_heartbeat,
                    metadata_json = excluded.metadata_json
                """,
                (
                    agent_id,
                    role,
                    status,
                    current_task,
                    float(confidence),
                    risk_level,
                    _json(item["permissions"]),
                    memory_scope,
                    item["last_heartbeat"],
                    _json(item["metadata"]),
                ),
            )
        return item

    def record_command(self, command: dict[str, Any]) -> dict[str, Any]:
        item = dict(command)
        item.setdefault("command_id", f"cmd_{uuid.uuid4().hex[:12]}")
        item.setdefault("created_at", utc_now())
        item.setdefault("metadata", {})
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_commands (
                    command_id, agent_id, task_id, proposal_id, command, cwd, status,
                    pid, exit_code, duration_ms, stdout_path, stderr_path, evidence_path,
                    risk_level, created_at, finished_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(command_id) DO UPDATE SET
                    status = excluded.status,
                    pid = excluded.pid,
                    exit_code = excluded.exit_code,
                    duration_ms = excluded.duration_ms,
                    stdout_path = excluded.stdout_path,
                    stderr_path = excluded.stderr_path,
                    evidence_path = excluded.evidence_path,
                    finished_at = excluded.finished_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    item["command_id"],
                    item.get("agent_id"),
                    item.get("task_id"),
                    item.get("proposal_id"),
                    item.get("command", ""),
                    item.get("cwd", ""),
                    item.get("status", "unknown"),
                    item.get("pid"),
                    item.get("exit_code"),
                    item.get("duration_ms"),
                    item.get("stdout_path"),
                    item.get("stderr_path"),
                    item.get("evidence_path"),
                    item.get("risk_level", "LOW"),
                    item["created_at"],
                    item.get("finished_at"),
                    _json(item["metadata"]),
                ),
            )
        return item

    def record_incident(
        self,
        *,
        severity: str,
        module: str,
        message: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        command_id: str | None = None,
        risk_level: str | None = None,
        sentry_event_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "id": f"inc_{uuid.uuid4().hex[:12]}",
            "severity": severity,
            "module": module,
            "message": message,
            "agent_id": agent_id,
            "task_id": task_id,
            "command_id": command_id,
            "risk_level": risk_level,
            "sentry_event_id": sentry_event_id,
            "metadata": metadata or {},
            "created_at": utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_incidents (
                    id, severity, module, message, agent_id, task_id, command_id,
                    risk_level, sentry_event_id, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    severity,
                    module,
                    message,
                    agent_id,
                    task_id,
                    command_id,
                    risk_level,
                    sentry_event_id,
                    _json(item["metadata"]),
                    item["created_at"],
                ),
            )
        return item

    def record_approval(self, approval: dict[str, Any]) -> dict[str, Any]:
        item = dict(approval)
        item.setdefault("created_at", utc_now())
        item.setdefault("updated_at", utc_now())
        item.setdefault("metadata", {})
        assessment = item.get("assessment") or {}
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_approvals (
                    proposal_id, approval_id, command, cwd, status, requested_by,
                    risk_level, impact, rollback, reason, created_at, updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    approval_id = excluded.approval_id,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    item["proposal_id"],
                    item.get("approval_id"),
                    item.get("command", ""),
                    item.get("cwd", ""),
                    item.get("status", "unknown"),
                    item.get("requested_by", "unknown"),
                    item.get("risk_level", "LOW"),
                    assessment.get("impact", ""),
                    assessment.get("rollback", ""),
                    item.get("reason", ""),
                    item["created_at"],
                    item["updated_at"],
                    _json(item["metadata"]),
                ),
            )
        return item

    def record_memory_entry(
        self,
        *,
        scope: str,
        kind: str,
        content: str,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "id": f"mem_{uuid.uuid4().hex[:12]}",
            "scope": scope,
            "kind": kind,
            "content": content,
            "source": source,
            "metadata": metadata or {},
            "created_at": utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_memory_entries (
                    id, scope, kind, content, source, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    scope,
                    kind,
                    content,
                    source,
                    _json(item["metadata"]),
                    item["created_at"],
                ),
            )
        return item

    def record_execution_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        item = dict(plan)
        item.setdefault("plan_id", f"plan_{uuid.uuid4().hex[:12]}")
        item.setdefault("status", "planned")
        item.setdefault("metadata", {})
        item.setdefault("created_at", utc_now())
        item["updated_at"] = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_execution_plans (
                    plan_id, task_id, command_id, proposal_id, title, objective,
                    status, metadata_json, created_at, updated_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id) DO UPDATE SET
                    task_id = excluded.task_id,
                    command_id = excluded.command_id,
                    proposal_id = excluded.proposal_id,
                    title = excluded.title,
                    objective = excluded.objective,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at,
                    finished_at = excluded.finished_at
                """,
                (
                    item["plan_id"],
                    item.get("task_id"),
                    item.get("command_id"),
                    item.get("proposal_id"),
                    item.get("title", "Execution plan"),
                    item.get("objective", ""),
                    item["status"],
                    _json(item["metadata"]),
                    item["created_at"],
                    item["updated_at"],
                    item.get("finished_at"),
                ),
            )
        return item

    def record_execution_step(self, step: dict[str, Any]) -> dict[str, Any]:
        item = dict(step)
        item.setdefault("step_id", f"step_{uuid.uuid4().hex[:12]}")
        item.setdefault("status", "pending")
        item.setdefault("evidence", {})
        item.setdefault("error", "")
        item.setdefault("created_at", utc_now())
        item["updated_at"] = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO org_execution_steps (
                    step_id, plan_id, step_index, title, action_type, status,
                    command_id, evidence_json, error, created_at, updated_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(step_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    step_index = excluded.step_index,
                    title = excluded.title,
                    action_type = excluded.action_type,
                    status = excluded.status,
                    command_id = excluded.command_id,
                    evidence_json = excluded.evidence_json,
                    error = excluded.error,
                    updated_at = excluded.updated_at,
                    finished_at = excluded.finished_at
                """,
                (
                    item["step_id"],
                    item["plan_id"],
                    int(item.get("step_index", 0)),
                    item.get("title", "Execution step"),
                    item.get("action_type", "generic"),
                    item["status"],
                    item.get("command_id"),
                    _json(item["evidence"]),
                    item.get("error", ""),
                    item["created_at"],
                    item["updated_at"],
                    item.get("finished_at"),
                ),
            )
        return item

    def update_execution_step(
        self,
        step_id: str,
        *,
        status: str,
        evidence: dict[str, Any] | None = None,
        error: str = "",
        finished: bool = False,
    ) -> dict[str, Any]:
        existing = self.get_execution_step(step_id)
        if not existing:
            raise KeyError(f"Execution step not found: {step_id}")
        merged = {
            **existing,
            "status": status,
            "evidence": evidence if evidence is not None else existing["evidence"],
            "error": error,
            "finished_at": utc_now() if finished else existing.get("finished_at"),
        }
        return self.record_execution_step(merged)

    def update_execution_plan(
        self,
        plan_id: str,
        *,
        status: str,
        metadata: dict[str, Any] | None = None,
        finished: bool = False,
    ) -> dict[str, Any]:
        existing = self.get_execution_plan(plan_id)
        if not existing:
            raise KeyError(f"Execution plan not found: {plan_id}")
        merged = {
            **existing,
            "status": status,
            "metadata": metadata if metadata is not None else existing["metadata"],
            "finished_at": utc_now() if finished else existing.get("finished_at"),
        }
        return self.record_execution_plan(merged)

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

    def list_agents(
        self, *, role: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_agents"
        params: list[Any] = []
        if role:
            query += " WHERE role = ?"
            params.append(role)
        query += " ORDER BY last_heartbeat DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "agent_id": row["agent_id"],
                "role": row["role"],
                "status": row["status"],
                "current_task": row["current_task"],
                "confidence": row["confidence"],
                "risk_level": row["risk_level"],
                "permissions": _loads(row["permissions_json"], default=[]),
                "memory_scope": row["memory_scope"],
                "last_heartbeat": row["last_heartbeat"],
                "metadata": _loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def list_commands(
        self,
        *,
        status: str | None = None,
        task_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_commands"
        params: list[Any] = []
        conditions = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "command_id": row["command_id"],
                "agent_id": row["agent_id"],
                "task_id": row["task_id"],
                "proposal_id": row["proposal_id"],
                "command": row["command"],
                "cwd": row["cwd"],
                "status": row["status"],
                "pid": row["pid"],
                "exit_code": row["exit_code"],
                "duration_ms": row["duration_ms"],
                "stdout_path": row["stdout_path"],
                "stderr_path": row["stderr_path"],
                "evidence_path": row["evidence_path"],
                "risk_level": row["risk_level"],
                "created_at": row["created_at"],
                "finished_at": row["finished_at"],
                "metadata": _loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def get_command(self, command_id: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM org_commands WHERE command_id = ?", [command_id]
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "command_id": row["command_id"],
            "agent_id": row["agent_id"],
            "task_id": row["task_id"],
            "proposal_id": row["proposal_id"],
            "command": row["command"],
            "cwd": row["cwd"],
            "status": row["status"],
            "pid": row["pid"],
            "exit_code": row["exit_code"],
            "duration_ms": row["duration_ms"],
            "stdout_path": row["stdout_path"],
            "stderr_path": row["stderr_path"],
            "evidence_path": row["evidence_path"],
            "risk_level": row["risk_level"],
            "created_at": row["created_at"],
            "finished_at": row["finished_at"],
            "metadata": _loads(row["metadata_json"]),
        }

    def list_incidents(
        self, *, severity: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_incidents"
        params: list[Any] = []
        if severity:
            query += " WHERE severity = ?"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "id": row["id"],
                "severity": row["severity"],
                "module": row["module"],
                "message": row["message"],
                "agent_id": row["agent_id"],
                "task_id": row["task_id"],
                "command_id": row["command_id"],
                "risk_level": row["risk_level"],
                "sentry_event_id": row["sentry_event_id"],
                "metadata": _loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_approvals(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_approvals"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetch(query, params)
        return [
            {
                "proposal_id": row["proposal_id"],
                "approval_id": row["approval_id"],
                "command": row["command"],
                "cwd": row["cwd"],
                "status": row["status"],
                "requested_by": row["requested_by"],
                "risk_level": row["risk_level"],
                "impact": row["impact"],
                "rollback": row["rollback"],
                "reason": row["reason"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "metadata": _loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def list_memory_entries(
        self, *, scope: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_memory_entries"
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
                "kind": row["kind"],
                "content": row["content"],
                "source": row["source"],
                "metadata": _loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_execution_plan(self, plan_id: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM org_execution_plans WHERE plan_id = ?", [plan_id]
        )
        if not rows:
            return None
        return self._execution_plan_from_row(rows[0])

    def list_execution_plans(
        self,
        *,
        status: str | None = None,
        task_id: str | None = None,
        command_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_execution_plans"
        params: list[Any] = []
        conditions = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)
        if command_id:
            conditions.append("command_id = ?")
            params.append(command_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [
            self._execution_plan_from_row(row) for row in self._fetch(query, params)
        ]

    def get_execution_step(self, step_id: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM org_execution_steps WHERE step_id = ?", [step_id]
        )
        if not rows:
            return None
        return self._execution_step_from_row(rows[0])

    def list_execution_steps(
        self,
        *,
        plan_id: str | None = None,
        command_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM org_execution_steps"
        params: list[Any] = []
        conditions = []
        if plan_id:
            conditions.append("plan_id = ?")
            params.append(plan_id)
        if command_id:
            conditions.append("command_id = ?")
            params.append(command_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if plan_id:
            query += " ORDER BY step_index ASC LIMIT ?"
        else:
            query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [
            self._execution_step_from_row(row) for row in self._fetch(query, params)
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
                "agents": conn.execute("SELECT COUNT(*) FROM org_agents").fetchone()[0],
                "commands": conn.execute(
                    "SELECT COUNT(*) FROM org_commands"
                ).fetchone()[0],
                "incidents": conn.execute(
                    "SELECT COUNT(*) FROM org_incidents"
                ).fetchone()[0],
                "approvals": conn.execute(
                    "SELECT COUNT(*) FROM org_approvals"
                ).fetchone()[0],
                "memory_entries": conn.execute(
                    "SELECT COUNT(*) FROM org_memory_entries"
                ).fetchone()[0],
                "execution_plans": conn.execute(
                    "SELECT COUNT(*) FROM org_execution_plans"
                ).fetchone()[0],
                "execution_steps": conn.execute(
                    "SELECT COUNT(*) FROM org_execution_steps"
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

    def _execution_plan_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "plan_id": row["plan_id"],
            "task_id": row["task_id"],
            "command_id": row["command_id"],
            "proposal_id": row["proposal_id"],
            "title": row["title"],
            "objective": row["objective"],
            "status": row["status"],
            "metadata": _loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "finished_at": row["finished_at"],
        }

    def _execution_step_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "step_id": row["step_id"],
            "plan_id": row["plan_id"],
            "step_index": row["step_index"],
            "title": row["title"],
            "action_type": row["action_type"],
            "status": row["status"],
            "command_id": row["command_id"],
            "evidence": _loads(row["evidence_json"]),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "finished_at": row["finished_at"],
        }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _loads(value: str, *, default: Any | None = None) -> Any:
    if default is None:
        default = {}
    return json.loads(value or _json(default))
