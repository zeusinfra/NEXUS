"""
ZEUS Cognitive Core — Reflection Engine.

Generates structured reflections at different depths:
  - cycle_reflection:  lightweight, runs every loop cycle
  - daily_reflection:  deep analysis, once per day
  - failure_reflection: triggered on action failure
  - improvement_reflection: triggered when system is idle

Reflections are persisted to ``cognitive_reflections`` and optionally
exported to Obsidian vault.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, date
from pathlib import Path

from zeus_core.cognitive.cognitive_db import get_connection
from zeus_core.observability import get_logger, log_event

logger = get_logger("zeus.cognitive.reflection")

VAULT_PATH = os.getenv("ZEUS_VAULT_PATH", "")
OBSIDIAN_SYNC = os.getenv("ZEUS_ENABLE_OBSIDIAN_AUTO_SYNC", "0").strip().lower() in {
    "1",
    "true",
    "yes",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Reflection:
    id: str
    type: str  # cycle | daily | failure | improvement
    summary: str = ""
    events: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    opportunities: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    learning: str = ""
    next_goals: list = field(default_factory=list)
    cycle_id: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ReflectionEngine:
    """Generates and persists cognitive reflections."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def cycle_reflection(
        self,
        *,
        cycle_id: str,
        perception_summary: str = "",
        analysis_summary: str = "",
        goals_created: int = 0,
        actions_executed: int = 0,
        actions_blocked: int = 0,
        errors: list[str] | None = None,
    ) -> Reflection:
        """Lightweight reflection generated at the end of each loop cycle."""
        summary_parts = []
        if perception_summary:
            summary_parts.append(f"Percepção: {perception_summary}")
        if analysis_summary:
            summary_parts.append(f"Análise: {analysis_summary}")
        summary_parts.append(f"Metas criadas: {goals_created}")
        summary_parts.append(
            f"Ações executadas: {actions_executed}, bloqueadas: {actions_blocked}"
        )

        reflection = Reflection(
            id=uuid.uuid4().hex[:12],
            type="cycle",
            summary="; ".join(summary_parts),
            failures=errors or [],
            cycle_id=cycle_id,
            created_at=_now_iso(),
        )
        self._persist(reflection)
        return reflection

    def daily_reflection(
        self,
        *,
        events_summary: list[str] | None = None,
        failures: list[str] | None = None,
        opportunities: list[str] | None = None,
        lessons_learned: list[str] | None = None,
        suggested_goals: list[str] | None = None,
        user_summary: str | None = None,
        cycle_count: int = 0,
        health_score: int = 100,
    ) -> Reflection:
        """Deep reflection intended to run once per day."""
        today = date.today().isoformat()
        summary = (
            f"Reflexão diária — {today}. "
            f"Ciclos executados: {cycle_count}. Score de saúde: {health_score}/100."
        )
        if user_summary:
            summary += f" Comportamento do usuário: {user_summary}"

        reflection = Reflection(
            id=uuid.uuid4().hex[:12],
            type="daily",
            summary=summary,
            events=events_summary or [],
            failures=failures or [],
            opportunities=opportunities or [],
            learning="; ".join(lessons_learned) if lessons_learned else "",
            next_goals=suggested_goals or [],
            created_at=_now_iso(),
        )
        self._persist(reflection)
        self._export_to_obsidian(reflection)
        log_event(logger, 20, "daily_reflection_created", reflection_id=reflection.id)
        return reflection

    def failure_reflection(
        self,
        *,
        error: str,
        context: str = "",
        goal_id: str | None = None,
        plan_id: str | None = None,
    ) -> Reflection:
        """Triggered when an action fails."""
        reflection = Reflection(
            id=uuid.uuid4().hex[:12],
            type="failure",
            summary=f"Falha detectada: {error[:200]}",
            failures=[error],
            events=[context] if context else [],
            learning=f"Investigar causa da falha. Goal: {goal_id}, Plan: {plan_id}",
            created_at=_now_iso(),
        )
        self._persist(reflection)
        log_event(logger, 30, "failure_reflection", error=error[:200], goal_id=goal_id)
        return reflection

    def improvement_reflection(
        self,
        *,
        opportunities: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> Reflection:
        """Triggered when the system is idle and can introspect."""
        reflection = Reflection(
            id=uuid.uuid4().hex[:12],
            type="improvement",
            summary="Reflexão de melhoria durante período ocioso.",
            opportunities=opportunities or [],
            actions=suggestions or [],
            created_at=_now_iso(),
        )
        self._persist(reflection)
        return reflection

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_reflections(
        self,
        *,
        reflection_type: str | None = None,
        limit: int = 20,
    ) -> list[Reflection]:
        query = "SELECT * FROM cognitive_reflections WHERE 1=1"
        params: list = []
        if reflection_type:
            query += " AND type = ?"
            params.append(reflection_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_reflection(r) for r in rows]

    def get_last_daily(self) -> Reflection | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_reflections WHERE type = 'daily' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return self._row_to_reflection(row) if row else None

    # ------------------------------------------------------------------
    # Obsidian Export
    # ------------------------------------------------------------------

    def _export_to_obsidian(self, reflection: Reflection) -> None:
        """Write a reflection to the Obsidian vault as Markdown."""
        if not OBSIDIAN_SYNC or not VAULT_PATH:
            return

        vault = Path(VAULT_PATH)
        if not vault.exists():
            return

        reflections_dir = vault / "ZEUS" / "Reflections"
        reflections_dir.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        filepath = reflections_dir / f"{today}.md"

        content = self._render_markdown(reflection, today)

        try:
            filepath.write_text(content, encoding="utf-8")
            log_event(logger, 20, "obsidian_reflection_exported", path=str(filepath))
        except Exception as e:
            log_event(logger, 40, "obsidian_export_failed", error=str(e))

    @staticmethod
    def _render_markdown(reflection: Reflection, date_str: str) -> str:
        lines = [
            f"# ZEUS Reflection — {date_str}",
            "",
            "## Resumo",
            reflection.summary or "Sem resumo disponível.",
            "",
        ]

        if reflection.events:
            lines.append("## Eventos importantes")
            for ev in reflection.events:
                lines.append(f"- {ev}")
            lines.append("")

        if reflection.failures:
            lines.append("## Falhas")
            for f in reflection.failures:
                lines.append(f"- {f}")
            lines.append("")

        if reflection.opportunities:
            lines.append("## Oportunidades")
            for o in reflection.opportunities:
                lines.append(f"- {o}")
            lines.append("")

        if reflection.next_goals:
            lines.append("## Metas sugeridas")
            for g in reflection.next_goals:
                lines.append(f"- {g}")
            lines.append("")

        if reflection.learning:
            lines.append("## Aprendizado")
            lines.append(reflection.learning)
            lines.append("")

        lines.append(
            f"---\n*Gerado automaticamente pelo ZEUS Cognitive Core em {reflection.created_at}*\n"
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _persist(self, r: Reflection) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO cognitive_reflections "
                "(id, type, summary, events, failures, opportunities, actions, learning, next_goals, cycle_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    r.id,
                    r.type,
                    r.summary,
                    json.dumps(r.events),
                    json.dumps(r.failures),
                    json.dumps(r.opportunities),
                    json.dumps(r.actions),
                    r.learning,
                    json.dumps(r.next_goals),
                    r.cycle_id,
                    r.created_at,
                ),
            )

    @staticmethod
    def _row_to_reflection(row) -> Reflection:
        def _parse(val):
            try:
                return json.loads(val) if isinstance(val, str) else (val or [])
            except (json.JSONDecodeError, TypeError):
                return []

        return Reflection(
            id=row["id"],
            type=row["type"],
            summary=row["summary"],
            events=_parse(row["events"]),
            failures=_parse(row["failures"]),
            opportunities=_parse(row["opportunities"]),
            actions=_parse(row["actions"]),
            learning=row["learning"] or "",
            next_goals=_parse(row["next_goals"]),
            cycle_id=row["cycle_id"],
            created_at=row["created_at"],
        )

    def export_goals_to_obsidian(self, goals: list) -> None:
        """Write active goals summary to Obsidian vault."""
        if not OBSIDIAN_SYNC or not VAULT_PATH:
            return

        vault = Path(VAULT_PATH)
        if not vault.exists():
            return

        goals_dir = vault / "ZEUS" / "Goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        filepath = goals_dir / "active_goals.md"

        lines = ["# ZEUS Active Goals", "", f"*Atualizado: {_now_iso()}*", ""]
        for g in goals:
            d = (
                g
                if isinstance(g, dict)
                else (g.to_dict() if hasattr(g, "to_dict") else {"title": str(g)})
            )
            status = d.get("status", "pending")
            priority = d.get("priority", "?")
            risk = d.get("risk", "?")
            lines.append(f"### [{status.upper()}] {d.get('title', 'Sem título')}")
            lines.append(f"- **Prioridade**: {priority} | **Risco**: {risk}")
            lines.append(f"- {d.get('description', '')}")
            lines.append("")

        try:
            filepath.write_text("\n".join(lines), encoding="utf-8")
            log_event(logger, 20, "obsidian_goals_exported", path=str(filepath))
        except Exception as e:
            log_event(logger, 40, "obsidian_goals_export_failed", error=str(e))
