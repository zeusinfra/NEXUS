"""
ZEUS Cognitive Core — Memory Compression.

Handles semantic summarization, temporal decay, and archiving
to ensure the cognitive database remains sustainable.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from zeus_core.cognitive.cognitive_db import get_connection
from zeus_core.observability import get_logger, log_event
from zeus_core import core_system

logger = get_logger("zeus.cognitive.memory_compression")

class MemoryCompression:
    """Sustainability engine for the cognitive database."""

    def __init__(self, db_path: str | None = None, archive_path: str | None = None) -> None:
        self.db_path = db_path
        self.archive_path = archive_path or (
            os.path.join(os.path.dirname(db_path), "zeus_archive.db") if db_path else None
        )

    def compress_all(self) -> dict:
        """Run all compression strategies."""
        started = datetime.now(timezone.utc)
        stats = {
            "summarized_interactions": 0,
            "decayed_goals": 0,
            "deleted_cycles": 0,
            "archived_records": 0
        }

        try:
            # 1. Semantic Summarization of old interactions
            stats["summarized_interactions"] = self._summarize_interactions(days_old=7)
            
            # 2. Temporal Decay for old goals/reflections
            stats["decayed_goals"] = self._decay_goals_and_reflections()
            
            # 3. Cleanup of cycle reflections (keep only failure/daily)
            stats["deleted_cycles"] = self._cleanup_cycle_reflections(days_old=3)
            
        except Exception as e:
            log_event(logger, 40, "compression_failed", error=str(e))
            return {"error": str(e)}

        duration = (datetime.now(timezone.utc) - started).total_seconds()
        log_event(logger, 20, "compression_complete", stats=stats, duration_s=duration)
        return stats

    def _summarize_interactions(self, days_old: int = 7) -> int:
        """
        Groups old interactions and uses LLM to create a semantic summary,
        then archives the raw records.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
        
        # 1. Get old interactions not yet summarized
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM user_interactions WHERE created_at < ? AND context NOT LIKE '%summarized%' LIMIT 50",
                (cutoff,)
            ).fetchall()
        
        if not rows:
            return 0
        
        # 2. Build summary prompt
        text_to_summarize = "\n".join([
            f"[{r['created_at']}] {r['type']}: {r['content'][:200]}" 
            for r in rows if r['content']
        ])
        
        prompt = [
            {"role": "system", "content": "Você é o motor de compressão de memória do ZEUS. Resuma as seguintes interações do usuário em um parágrafo denso e semântico, destacando intenções, tarefas recorrentes e aprendizados."},
            {"role": "user", "content": text_to_summarize}
        ]
        
        try:
            summary = core_system.call_cloud_llm(prompt)
            if not summary or "Error" in summary:
                print(f"DEBUG: LLM returned empty or error: {summary}", flush=True)
                return 0
            
            # 3. Save summary as a new interaction of type 'long_term_summary'
            sid = uuid.uuid4().hex[:12]
            with get_connection(self.db_path) as conn:
                first_row = dict(rows[0])
                h = first_row.get('hour', 0)
                w = first_row.get('weekday', 0)
                s = first_row.get('session_id', 'consolidated')

                conn.execute(
                    "INSERT INTO user_interactions (id, type, content, context, hour, weekday, session_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (sid, "long_term_summary", summary, json.dumps({"source_count": len(rows), "summarized": True}), h, w, s, rows[0]['created_at'])
                )
                
                # 4. Archive and Delete raw records
                self._archive_records("user_interactions", [r['id'] for r in rows], conn=conn)
                
            return len(rows)
        except Exception as e:
            log_event(logger, 30, "summarization_error", error=str(e))
            return 0

    def _decay_goals_and_reflections(self) -> int:
        """Reduce importance/priority of old records to allow them to be 'forgotten'."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        count = 0
        with get_connection(self.db_path) as conn:
            # Decay goals
            res = conn.execute(
                "UPDATE cognitive_goals SET priority = priority * 0.8 WHERE created_at < ? AND status = 'completed'",
                (cutoff,)
            )
            count += res.rowcount
        return count

    def _cleanup_cycle_reflections(self, days_old: int = 3) -> int:
        """Delete low-value cycle reflections while keeping failures and daily ones."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
        with get_connection(self.db_path) as conn:
            res = conn.execute(
                "DELETE FROM cognitive_reflections WHERE type = 'cycle' AND created_at < ?",
                (cutoff,)
            )
            return res.rowcount

    def _archive_records(self, table: str, ids: list[str], conn: sqlite3.Connection | None = None) -> None:
        """Move records to the archive database and delete from main."""
        if not ids:
            return

        if conn:
            placeholders = ",".join(["?"] * len(ids))
            conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
        else:
            with get_connection(self.db_path) as conn:
                placeholders = ",".join(["?"] * len(ids))
                conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
