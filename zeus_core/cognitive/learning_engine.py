"""
ZEUS Cognitive Core — Learning Engine.

Learns from execution results, stores operational lessons,
detects repeated failures, and adjusts goal priorities.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from zeus_core.cognitive.cognitive_db import get_connection
from zeus_core.observability import get_logger, log_event

logger = get_logger("zeus.cognitive.learning")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Lesson:
    id: str
    lesson: str
    source: str = "execution"  # execution | failure | pattern | reflection
    confidence: float = 0.5
    tags: list = None
    created_at: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> dict:
        return asdict(self)


class CognitiveLearningEngine:
    """Learns from cognitive loop outcomes and persists lessons."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Learning from results
    # ------------------------------------------------------------------

    def learn_from_result(
        self,
        goal,
        plan,
        results: list,
    ) -> Lesson | None:
        """Evaluate execution results and extract a lesson."""
        goal_dict = goal.to_dict() if hasattr(goal, "to_dict") else goal

        # Count outcomes
        successes = sum(1 for r in results if self._status(r) == "success")
        failures = sum(1 for r in results if self._status(r) == "failed")
        blocked = sum(1 for r in results if self._status(r) == "blocked")
        total = len(results)

        if total == 0:
            return None

        # Determine lesson
        goal_title = goal_dict.get("title", "meta desconhecida")
        goal_type = goal_dict.get("type", "operational")

        if failures > 0:
            error_msgs = [self._error(r) for r in results if self._error(r)]
            lesson_text = (
                f"Meta '{goal_title}' teve {failures}/{total} etapas com falha. "
                f"Erros: {'; '.join(error_msgs[:3])}"
            )
            source = "failure"
            confidence = 0.7
            tags = [goal_type, "failure"]
        elif blocked > 0:
            lesson_text = (
                f"Meta '{goal_title}' teve {blocked}/{total} etapas bloqueadas por política de segurança. "
                f"Considerar abordagem alternativa."
            )
            source = "pattern"
            confidence = 0.6
            tags = [goal_type, "blocked", "security"]
        elif successes == total:
            lesson_text = (
                f"Meta '{goal_title}' executada com sucesso total ({successes} etapas)."
            )
            source = "execution"
            confidence = 0.9
            tags = [goal_type, "success"]
        else:
            lesson_text = (
                f"Meta '{goal_title}': {successes} sucessos, {failures} falhas, "
                f"{blocked} bloqueios em {total} etapas."
            )
            source = "execution"
            confidence = 0.5
            tags = [goal_type, "mixed"]

        return self.store_lesson(
            lesson_text, source=source, confidence=confidence, tags=tags
        )

    # ------------------------------------------------------------------
    # Goal priority adjustment
    # ------------------------------------------------------------------

    def update_goal_priority(self, goal, results: list) -> int:
        """Return a priority delta based on execution outcomes."""
        successes = sum(1 for r in results if self._status(r) == "success")
        failures = sum(1 for r in results if self._status(r) == "failed")
        total = len(results)

        if total == 0:
            return 0

        success_rate = successes / total

        if success_rate >= 0.8:
            # Goal was achievable — lower priority (it's handled)
            return -10
        elif failures > successes:
            # Goal keeps failing — raise priority for investigation
            return 5
        return 0

    # ------------------------------------------------------------------
    # Repeated failure detection
    # ------------------------------------------------------------------

    def detect_repeated_failures(self, threshold: int = 3) -> list[dict]:
        """Find goals or patterns that fail repeatedly."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT lesson, COUNT(*) as cnt FROM cognitive_lessons "
                "WHERE source = 'failure' "
                "GROUP BY lesson HAVING cnt >= ? "
                "ORDER BY cnt DESC LIMIT 10",
                (threshold,),
            ).fetchall()

        failures = []
        for row in rows:
            failures.append(
                {
                    "lesson": row["lesson"],
                    "count": row["cnt"],
                }
            )

        if failures:
            log_event(logger, 30, "repeated_failures_detected", count=len(failures))

        return failures

    # ------------------------------------------------------------------
    # Lesson storage
    # ------------------------------------------------------------------

    def store_lesson(
        self,
        lesson: str,
        *,
        source: str = "execution",
        confidence: float = 0.5,
        tags: list | None = None,
    ) -> Lesson:
        """Persist a lesson to the database."""
        entry = Lesson(
            id=uuid.uuid4().hex[:12],
            lesson=lesson,
            source=source,
            confidence=max(0.0, min(1.0, confidence)),
            tags=tags or [],
            created_at=_now_iso(),
        )

        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO cognitive_lessons (id, lesson, source, confidence, tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry.id,
                    entry.lesson,
                    entry.source,
                    entry.confidence,
                    json.dumps(entry.tags),
                    entry.created_at,
                ),
            )

        log_event(
            logger,
            20,
            "lesson_stored",
            lesson_id=entry.id,
            source=source,
            confidence=confidence,
        )
        return entry

    def list_lessons(
        self, *, limit: int = 20, source: str | None = None
    ) -> list[Lesson]:
        query = "SELECT * FROM cognitive_lessons WHERE 1=1"
        params: list = []
        if source:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_lesson(r) for r in rows]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _status(result) -> str:
        if hasattr(result, "status"):
            return result.status
        if isinstance(result, dict):
            return result.get("status", "unknown")
        return "unknown"

    @staticmethod
    def _error(result) -> str:
        if hasattr(result, "error"):
            return result.error
        if isinstance(result, dict):
            return result.get("error", "")
        return ""

    @staticmethod
    def _row_to_lesson(row) -> Lesson:
        tags = row["tags"]
        try:
            tags = json.loads(tags) if isinstance(tags, str) else (tags or [])
        except (json.JSONDecodeError, TypeError):
            tags = []
        return Lesson(
            id=row["id"],
            lesson=row["lesson"],
            source=row["source"],
            confidence=row["confidence"],
            tags=tags,
            created_at=row["created_at"],
        )
