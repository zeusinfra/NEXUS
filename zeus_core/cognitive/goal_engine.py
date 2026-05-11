"""
ZEUS Cognitive Core — Goal Engine.

Creates, manages, and deduplicates autonomous goals.
Goals are persisted to the ``cognitive_goals`` table in SQLite.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from zeus_core.cognitive.cognitive_db import get_connection
from zeus_core.observability import get_logger, log_event

logger = get_logger("zeus.cognitive.goals")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


VALID_TYPES = {
    "operational",
    "cognitive",
    "security",
    "performance",
    "ux",
    "maintenance",
}
VALID_ORIGINS = {"system_analysis", "user_request", "reflection", "watcher", "error"}
VALID_RISKS = {"low", "medium", "high", "critical"}
VALID_STATUSES = {
    "pending",
    "planned",
    "blocked",
    "requires_confirmation",
    "executing",
    "done",
    "failed",
}


@dataclass
class CognitiveGoal:
    id: str
    title: str
    description: str = ""
    type: str = "operational"
    origin: str = "system_analysis"
    priority: int = 50
    risk: str = "low"
    status: str = "pending"
    evidence: list = field(default_factory=list)
    plan_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class GoalEngine:
    """Manages the lifecycle of cognitive goals."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_goal(
        self,
        title: str,
        *,
        description: str = "",
        goal_type: str = "operational",
        origin: str = "system_analysis",
        priority: int = 50,
        risk: str = "low",
        evidence: list | None = None,
    ) -> CognitiveGoal | None:
        """Create a goal if no near-duplicate exists. Returns None if deduplicated."""
        if goal_type not in VALID_TYPES:
            goal_type = "operational"
        if origin not in VALID_ORIGINS:
            origin = "system_analysis"
        if risk not in VALID_RISKS:
            risk = "low"
        priority = max(1, min(100, priority))

        # Security goals get a priority floor
        if goal_type == "security" and priority < 70:
            priority = 70

        # Deduplication check
        if self._is_duplicate(title):
            log_event(logger, 20, "goal_deduplicated", title=title)
            return None

        now = _now_iso()
        goal = CognitiveGoal(
            id=uuid.uuid4().hex[:12],
            title=title,
            description=description,
            type=goal_type,
            origin=origin,
            priority=priority,
            risk=risk,
            status="pending",
            evidence=evidence or [],
            created_at=now,
            updated_at=now,
        )

        self._persist(goal)
        log_event(
            logger,
            20,
            "goal_created",
            goal_id=goal.id,
            title=title,
            priority=priority,
            risk=risk,
        )
        return goal

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_goals(self, limit: int = 20) -> list[CognitiveGoal]:
        """Return pending/planned goals ordered by priority desc."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM cognitive_goals WHERE status IN ('pending','planned') "
                "ORDER BY priority DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def list_goals(
        self,
        *,
        status: str | None = None,
        goal_type: str | None = None,
        limit: int = 50,
    ) -> list[CognitiveGoal]:
        """List goals with optional filters."""
        query = "SELECT * FROM cognitive_goals WHERE 1=1"
        params: list = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if goal_type:
            query += " AND type = ?"
            params.append(goal_type)
        query += " ORDER BY priority DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def get_goal(self, goal_id: str) -> CognitiveGoal | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_goals WHERE id = ?", (goal_id,)
            ).fetchone()
        return self._row_to_goal(row) if row else None

    def count_by_status(self) -> dict[str, int]:
        """Return {status: count} for all goals."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM cognitive_goals GROUP BY status"
            ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    def update_status(self, goal_id: str, new_status: str) -> bool:
        if new_status not in VALID_STATUSES:
            return False
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE cognitive_goals SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, _now_iso(), goal_id),
            )
        log_event(logger, 20, "goal_status_updated", goal_id=goal_id, status=new_status)
        return True

    def link_plan(self, goal_id: str, plan_id: str) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE cognitive_goals SET plan_id = ?, status = 'planned', updated_at = ? WHERE id = ?",
                (plan_id, _now_iso(), goal_id),
            )

    def adjust_priority(self, goal_id: str, delta: int) -> None:
        """Shift priority by delta, clamped to [1, 100]."""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE cognitive_goals SET priority = MAX(1, MIN(100, priority + ?)), updated_at = ? WHERE id = ?",
                (delta, _now_iso(), goal_id),
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _is_duplicate(self, title: str) -> bool:
        """Check if an active goal with the same title already exists."""
        normalized = title.strip().lower()
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT title FROM cognitive_goals WHERE status NOT IN ('done', 'failed')"
            ).fetchall()
        for row in rows:
            existing = (row["title"] or "").strip().lower()
            if existing == normalized:
                return True
            # Fuzzy: if one title contains the other and they're long enough
            if len(normalized) > 15 and len(existing) > 15:
                if normalized in existing or existing in normalized:
                    return True
        return False

    def _persist(self, goal: CognitiveGoal) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO cognitive_goals "
                "(id, title, description, type, origin, priority, risk, status, evidence, plan_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    goal.id,
                    goal.title,
                    goal.description,
                    goal.type,
                    goal.origin,
                    goal.priority,
                    goal.risk,
                    goal.status,
                    json.dumps(goal.evidence),
                    goal.plan_id,
                    goal.created_at,
                    goal.updated_at,
                ),
            )

    @staticmethod
    def _row_to_goal(row: dict) -> CognitiveGoal:
        evidence = row["evidence"]
        try:
            evidence = json.loads(evidence) if isinstance(evidence, str) else evidence
        except (json.JSONDecodeError, TypeError):
            evidence = []
        return CognitiveGoal(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            type=row["type"],
            origin=row["origin"],
            priority=row["priority"],
            risk=row["risk"],
            status=row["status"],
            evidence=evidence,
            plan_id=row["plan_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
