"""
ZEUS Cognitive Core — User Profile Engine.

Tracks user behavior, synthesizes habits, detects workflows,
and builds temporal context for cognitive loop awareness.
"""
from __future__ import annotations

import json
import os
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from typing import Any

from zeus_core.cognitive.cognitive_db import get_connection
from zeus_core.observability import get_logger, log_event

logger = get_logger("zeus.cognitive.profile")

SESSION_GAP_MINUTES = 5
VAULT_PATH = os.getenv("ZEUS_VAULT_PATH", "")
OBSIDIAN_SYNC = os.getenv("ZEUS_ENABLE_OBSIDIAN_AUTO_SYNC", "0").strip().lower() in {"1", "true", "yes"}

PERIOD_LABELS = {
    range(6, 12): "morning",
    range(12, 14): "afternoon_early",
    range(14, 18): "afternoon",
    range(18, 21): "evening",
    range(21, 24): "night",
    range(0, 6): "late_night",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _now_local() -> datetime:
    return datetime.now()


def _period_label(hour: int) -> str:
    for r, label in PERIOD_LABELS.items():
        if hour in r:
            return label
    return "night"


@dataclass
class TemporalContext:
    current_hour: int = 0
    current_weekday: int = 0
    is_work_hours: bool = False
    is_deep_focus: bool = False
    is_late_night: bool = False
    active_session: str | None = None
    session_duration_min: int = 0
    expected_habits: list[str] = field(default_factory=list)
    active_workflow: str | None = None
    period_label: str = "night"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UserInteraction:
    id: str
    type: str
    content: str = ""
    context: str = ""
    hour: int = 0
    weekday: int = 0
    session_id: str | None = None
    created_at: str = ""


@dataclass
class UserHabit:
    id: str
    name: str
    time_range: str = "00:00-23:59"
    weekdays: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    avg_duration_m: float = 0
    frequency: str = "daily"
    tools: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    confidence: float = 0.5
    last_observed: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class UserWorkflow:
    id: str
    name: str
    description: str = ""
    steps: list[str] = field(default_factory=list)
    trigger: str = ""
    frequency: str = "daily"
    avg_duration_m: float = 0
    confidence: float = 0.5
    last_observed: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------
# Module-level recording function (fire-and-forget from chat handler)
# ------------------------------------------------------------------

def record_interaction(
    interaction_type: str,
    content: str = "",
    context: str = "",
    db_path: str | None = None,
) -> str:
    """Record a user interaction. Returns the interaction id."""
    now = _now_local()
    iid = uuid.uuid4().hex[:12]
    session_id = _resolve_session(interaction_type, now, db_path)

    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO user_interactions "
            "(id, type, content, context, hour, weekday, session_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (iid, interaction_type, content[:2000], context[:500],
             now.hour, now.weekday(), session_id, _now_iso()),
        )
    return iid


def _resolve_session(itype: str, now: datetime, db_path: str | None = None) -> str:
    """Find the current session or create a new one."""
    cutoff = (now - timedelta(minutes=SESSION_GAP_MINUTES)).isoformat(timespec="seconds")
    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT session_id FROM user_interactions "
                "WHERE created_at > ? AND session_id IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1",
                (cutoff,),
            ).fetchone()
        if row and row["session_id"]:
            return row["session_id"]
    except Exception:
        pass
    return f"s-{uuid.uuid4().hex[:8]}"


class UserProfileEngine:
    """Central engine for user behavior analysis."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Temporal Context
    # ------------------------------------------------------------------

    def build_temporal_context(self) -> TemporalContext:
        """Build a fresh temporal context for the current moment."""
        now = _now_local()
        hour = now.hour
        weekday = now.weekday()
        period = _period_label(hour)

        # Check active session
        session_id, session_dur = self._get_active_session()

        # Determine deep focus (session > 30 min with recent activity)
        is_deep = session_dur >= 30

        # Check expected habits
        expected = self._get_expected_habits(hour, weekday)

        # Detect work hours from habits or default 9-18
        is_work = self._is_work_hours(hour, weekday)

        # Detect active workflow
        active_wf = self._detect_active_workflow(session_id) if session_id else None

        return TemporalContext(
            current_hour=hour,
            current_weekday=weekday,
            is_work_hours=is_work,
            is_deep_focus=is_deep,
            is_late_night=period == "late_night",
            active_session=session_id,
            session_duration_min=session_dur,
            expected_habits=[h["name"] for h in expected],
            active_workflow=active_wf,
            period_label=period,
        )

    def get_current_session_summary(self) -> dict:
        """Return summary of the current session."""
        session_id, duration = self._get_active_session()
        if not session_id:
            return {"active": False}

        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT type, COUNT(*) as cnt FROM user_interactions "
                "WHERE session_id = ? GROUP BY type",
                (session_id,),
            ).fetchall()

        return {
            "active": True,
            "session_id": session_id,
            "duration_min": duration,
            "interaction_counts": {r["type"]: r["cnt"] for r in rows},
        }

    # ------------------------------------------------------------------
    # Habit Synthesis
    # ------------------------------------------------------------------

    def synthesize_habits(self) -> list[UserHabit]:
        """Analyze recent interactions and create/update habit patterns."""
        habits: list[UserHabit] = []

        # Get interactions from the last 14 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(timespec="seconds")
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT type, hour, weekday, session_id, created_at "
                "FROM user_interactions WHERE created_at > ? ORDER BY created_at",
                (cutoff,),
            ).fetchall()

        if not rows:
            return habits

        # Group by hour buckets (3-hour windows)
        hour_buckets: dict[int, list] = defaultdict(list)
        for r in rows:
            bucket = (r["hour"] // 3) * 3  # 0,3,6,9,12,15,18,21
            hour_buckets[bucket].append(dict(r))

        # Detect patterns per bucket
        for bucket_start, interactions in hour_buckets.items():
            if len(interactions) < 3:
                continue

            bucket_end = bucket_start + 3
            types = Counter(i["type"] for i in interactions)
            weekdays = Counter(i["weekday"] for i in interactions)
            dominant_type = types.most_common(1)[0][0]
            active_days = sorted(weekdays.keys())

            # Determine frequency
            day_count = len(set(i["created_at"][:10] for i in interactions))
            if day_count >= 10:
                freq = "daily"
            elif all(d < 5 for d in active_days):
                freq = "weekday"
            elif all(d >= 5 for d in active_days):
                freq = "weekend"
            else:
                freq = "sporadic"

            # Name the habit
            name = f"{dominant_type}_{_period_label(bucket_start)}"
            confidence = min(1.0, len(interactions) / 20.0)

            habit = UserHabit(
                id=uuid.uuid4().hex[:12],
                name=name,
                time_range=f"{bucket_start:02d}:00-{bucket_end:02d}:00",
                weekdays=active_days,
                avg_duration_m=0,
                frequency=freq,
                tools=[],
                topics=list(set(i.get("context", "") for i in interactions if i.get("context")))[:10],
                confidence=confidence,
                last_observed=interactions[-1]["created_at"],
                created_at=_now_iso(),
            )

            self._upsert_habit(habit)
            habits.append(habit)

        # Decay old habits
        self._decay_habits()

        log_event(logger, 20, "habits_synthesized", count=len(habits))
        return habits

    # ------------------------------------------------------------------
    # Workflow Detection
    # ------------------------------------------------------------------

    def detect_workflows(self) -> list[UserWorkflow]:
        """Detect repeated action sequences across sessions."""
        workflows: list[UserWorkflow] = []

        # Get sessions from the last 7 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
        with get_connection(self.db_path) as conn:
            sessions = conn.execute(
                "SELECT DISTINCT session_id FROM user_interactions "
                "WHERE created_at > ? AND session_id IS NOT NULL",
                (cutoff,),
            ).fetchall()

        if len(sessions) < 2:
            return workflows

        # Build action sequences per session
        sequences: list[list[str]] = []
        for s in sessions:
            sid = s["session_id"]
            with get_connection(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT type, context FROM user_interactions "
                    "WHERE session_id = ? ORDER BY created_at",
                    (sid,),
                ).fetchall()
            seq = [f"{r['type']}:{r['context']}" if r["context"] else r["type"] for r in rows]
            if len(seq) >= 2:
                sequences.append(seq)

        # Find common subsequences (simplified: look for common bigrams/trigrams)
        bigram_counts: Counter = Counter()
        trigram_counts: Counter = Counter()

        for seq in sequences:
            seen_bi = set()
            seen_tri = set()
            for i in range(len(seq) - 1):
                bi = (seq[i], seq[i + 1])
                if bi not in seen_bi:
                    bigram_counts[bi] += 1
                    seen_bi.add(bi)
            for i in range(len(seq) - 2):
                tri = (seq[i], seq[i + 1], seq[i + 2])
                if tri not in seen_tri:
                    trigram_counts[tri] += 1
                    seen_tri.add(tri)

        # Create workflows from repeated patterns
        for pattern, count in trigram_counts.most_common(5):
            if count < 2:
                break
            steps = list(pattern)
            name = f"workflow_{'_'.join(s.split(':')[0] for s in steps[:2])}"
            confidence = min(1.0, count / len(sequences))

            wf = UserWorkflow(
                id=uuid.uuid4().hex[:12],
                name=name,
                description=f"Sequência detectada em {count}/{len(sequences)} sessões",
                steps=steps,
                trigger=steps[0],
                frequency="daily" if count >= 5 else "sporadic",
                confidence=confidence,
                last_observed=_now_iso(),
                created_at=_now_iso(),
            )
            self._upsert_workflow(wf)
            workflows.append(wf)

        log_event(logger, 20, "workflows_detected", count=len(workflows))
        return workflows

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_habits(self, limit: int = 20) -> list[UserHabit]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM user_habits ORDER BY confidence DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_habit(r) for r in rows]

    def list_workflows(self, limit: int = 20) -> list[UserWorkflow]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM user_workflows ORDER BY confidence DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_workflow(r) for r in rows]

    def get_interaction_stats(self, days: int = 7) -> dict:
        """Return interaction statistics for the last N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        with get_connection(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM user_interactions WHERE created_at > ?", (cutoff,)
            ).fetchone()["cnt"]
            by_type = conn.execute(
                "SELECT type, COUNT(*) as cnt FROM user_interactions "
                "WHERE created_at > ? GROUP BY type ORDER BY cnt DESC", (cutoff,)
            ).fetchall()
            by_hour = conn.execute(
                "SELECT hour, COUNT(*) as cnt FROM user_interactions "
                "WHERE created_at > ? GROUP BY hour ORDER BY hour", (cutoff,)
            ).fetchall()
        return {
            "total_interactions": total,
            "by_type": {r["type"]: r["cnt"] for r in by_type},
            "by_hour": {r["hour"]: r["cnt"] for r in by_hour},
            "period_days": days,
        }

    def get_profile_summary(self) -> dict:
        """Full profile summary for API endpoint."""
        temporal = self.build_temporal_context()
        session = self.get_current_session_summary()
        habits = self.list_habits(limit=10)
        workflows = self.list_workflows(limit=5)
        stats = self.get_interaction_stats(days=7)

        return {
            "temporal": temporal.to_dict(),
            "session": session,
            "habits": [h.to_dict() for h in habits],
            "workflows": [w.to_dict() for w in workflows],
            "stats": stats,
        }

    # ------------------------------------------------------------------
    # Obsidian Export
    # ------------------------------------------------------------------

    def export_profile_to_obsidian(self) -> None:
        """Write user profile to Obsidian vault."""
        if not OBSIDIAN_SYNC or not VAULT_PATH:
            return
        vault = Path(VAULT_PATH)
        if not vault.exists():
            return

        profile_dir = vault / "ZEUS" / "Profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        temporal = self.build_temporal_context()
        habits = self.list_habits()
        workflows = self.list_workflows()
        stats = self.get_interaction_stats()
        today = date.today().isoformat()

        lines = [
            f"# ZEUS User Profile — {today}",
            "",
            "## Contexto Temporal",
            f"- **Período**: {temporal.period_label}",
            f"- **Horário de trabalho**: {'Sim' if temporal.is_work_hours else 'Não'}",
            f"- **Foco profundo**: {'Sim' if temporal.is_deep_focus else 'Não'}",
            f"- **Sessão ativa**: {temporal.session_duration_min}min",
            "",
        ]

        if habits:
            lines.append("## Hábitos Detectados")
            for h in habits:
                lines.append(f"### {h.name} ({h.frequency})")
                lines.append(f"- Horário: {h.time_range}")
                lines.append(f"- Confiança: {h.confidence:.0%}")
                if h.topics:
                    lines.append(f"- Tópicos: {', '.join(h.topics[:5])}")
                lines.append("")

        if workflows:
            lines.append("## Workflows Detectados")
            for w in workflows:
                lines.append(f"### {w.name}")
                lines.append(f"- {w.description}")
                lines.append(f"- Etapas: {' → '.join(w.steps[:5])}")
                lines.append("")

        if stats:
            lines.append("## Estatísticas (7 dias)")
            lines.append(f"- Total de interações: {stats['total_interactions']}")
            for t, c in stats.get("by_type", {}).items():
                lines.append(f"  - {t}: {c}")
            lines.append("")

        lines.append(f"---\n*Atualizado: {_now_iso()}*\n")

        try:
            (profile_dir / "daily_profile.md").write_text("\n".join(lines), encoding="utf-8")
            log_event(logger, 20, "profile_exported_obsidian")
        except Exception as e:
            log_event(logger, 40, "profile_export_failed", error=str(e))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_active_session(self) -> tuple[str | None, int]:
        """Return (session_id, duration_minutes) of current active session."""
        cutoff = (_now_local() - timedelta(minutes=SESSION_GAP_MINUTES)).isoformat(timespec="seconds")
        try:
            with get_connection(self.db_path) as conn:
                row = conn.execute(
                    "SELECT session_id, MIN(created_at) as start_at, MAX(created_at) as end_at "
                    "FROM user_interactions WHERE created_at > ? AND session_id IS NOT NULL "
                    "GROUP BY session_id ORDER BY end_at DESC LIMIT 1",
                    (cutoff,),
                ).fetchone()
            if not row or not row["session_id"]:
                return None, 0
            try:
                start = datetime.fromisoformat(row["start_at"])
                end = datetime.fromisoformat(row["end_at"])
                dur = max(0, int((end - start).total_seconds() / 60))
            except Exception:
                dur = 0
            return row["session_id"], dur
        except Exception:
            return None, 0

    def _get_expected_habits(self, hour: int, weekday: int) -> list[dict]:
        """Return habits that typically occur at this hour/weekday."""
        try:
            with get_connection(self.db_path) as conn:
                rows = conn.execute("SELECT * FROM user_habits WHERE confidence > 0.3").fetchall()
            results = []
            for r in rows:
                try:
                    wds = json.loads(r["weekdays"]) if isinstance(r["weekdays"], str) else r["weekdays"]
                except Exception:
                    wds = []
                if weekday not in wds:
                    continue
                tr = r["time_range"]
                try:
                    start_h = int(tr.split("-")[0].split(":")[0])
                    end_h = int(tr.split("-")[1].split(":")[0])
                    if start_h <= hour < end_h:
                        results.append(dict(r))
                except Exception:
                    continue
            return results
        except Exception:
            return []

    def _is_work_hours(self, hour: int, weekday: int) -> bool:
        """Determine if current time is work hours based on habits or default."""
        habits = self._get_expected_habits(hour, weekday)
        if habits:
            return True
        # Default: Mon-Fri 9-18
        return weekday < 5 and 9 <= hour < 18

    def _detect_active_workflow(self, session_id: str) -> str | None:
        """Check if current session matches a known workflow."""
        try:
            with get_connection(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT type FROM user_interactions WHERE session_id = ? ORDER BY created_at",
                    (session_id,),
                ).fetchall()
                wfs = conn.execute("SELECT name, steps FROM user_workflows WHERE confidence > 0.3").fetchall()

            if not rows or not wfs:
                return None

            current_types = [r["type"] for r in rows]
            for wf in wfs:
                try:
                    steps = json.loads(wf["steps"]) if isinstance(wf["steps"], str) else wf["steps"]
                except Exception:
                    continue
                step_types = [s.split(":")[0] for s in steps]
                if len(step_types) <= len(current_types):
                    if current_types[:len(step_types)] == step_types:
                        return wf["name"]
            return None
        except Exception:
            return None

    def _upsert_habit(self, habit: UserHabit) -> None:
        with get_connection(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM user_habits WHERE name = ?", (habit.name,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE user_habits SET time_range=?, weekdays=?, frequency=?, "
                    "topics=?, confidence=?, last_observed=? WHERE name=?",
                    (habit.time_range, json.dumps(habit.weekdays), habit.frequency,
                     json.dumps(habit.topics), habit.confidence, habit.last_observed, habit.name),
                )
            else:
                conn.execute(
                    "INSERT INTO user_habits "
                    "(id, name, time_range, weekdays, avg_duration_m, frequency, tools, topics, confidence, last_observed, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (habit.id, habit.name, habit.time_range, json.dumps(habit.weekdays),
                     habit.avg_duration_m, habit.frequency, json.dumps(habit.tools),
                     json.dumps(habit.topics), habit.confidence, habit.last_observed, habit.created_at),
                )

    def _upsert_workflow(self, wf: UserWorkflow) -> None:
        with get_connection(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM user_workflows WHERE name = ?", (wf.name,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE user_workflows SET steps=?, description=?, frequency=?, "
                    "confidence=?, last_observed=? WHERE name=?",
                    (json.dumps(wf.steps), wf.description, wf.frequency,
                     wf.confidence, wf.last_observed, wf.name),
                )
            else:
                conn.execute(
                    "INSERT INTO user_workflows "
                    "(id, name, description, steps, trigger, frequency, avg_duration_m, confidence, last_observed, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (wf.id, wf.name, wf.description, json.dumps(wf.steps), wf.trigger,
                     wf.frequency, wf.avg_duration_m, wf.confidence, wf.last_observed, wf.created_at),
                )

    def _decay_habits(self, max_age_days: int = 7) -> None:
        """Reduce confidence of habits not observed recently."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat(timespec="seconds")
        try:
            with get_connection(self.db_path) as conn:
                conn.execute(
                    "UPDATE user_habits SET confidence = MAX(0.1, confidence * 0.8) "
                    "WHERE last_observed < ?",
                    (cutoff,),
                )
        except Exception:
            pass

    @staticmethod
    def _row_to_habit(row) -> UserHabit:
        def _jparse(v):
            try:
                return json.loads(v) if isinstance(v, str) else (v or [])
            except Exception:
                return []
        return UserHabit(
            id=row["id"], name=row["name"], time_range=row["time_range"],
            weekdays=_jparse(row["weekdays"]), avg_duration_m=row["avg_duration_m"],
            frequency=row["frequency"], tools=_jparse(row["tools"]),
            topics=_jparse(row["topics"]), confidence=row["confidence"],
            last_observed=row["last_observed"], created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_workflow(row) -> UserWorkflow:
        def _jparse(v):
            try:
                return json.loads(v) if isinstance(v, str) else (v or [])
            except Exception:
                return []
        return UserWorkflow(
            id=row["id"], name=row["name"], description=row["description"],
            steps=_jparse(row["steps"]), trigger=row["trigger"],
            frequency=row["frequency"], avg_duration_m=row["avg_duration_m"],
            confidence=row["confidence"], last_observed=row["last_observed"],
            created_at=row["created_at"],
        )
