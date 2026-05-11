import pytest
import json
import datetime
from unittest.mock import patch
from zeus_core.cognitive.cognitive_db import init_cognitive_tables, get_connection
from zeus_core.cognitive.memory_compression import MemoryCompression


@pytest.fixture
def mc(tmp_path):
    db = str(tmp_path / "test_memory.db")
    init_cognitive_tables(db)
    return MemoryCompression(db_path=db)


class TestMemoryCompression:
    def test_cleanup_cycle_reflections(self, mc):
        with get_connection(mc.db_path) as conn:
            # Insert some old cycle reflections
            conn.execute(
                "INSERT INTO cognitive_reflections (id, type, summary, created_at) VALUES "
                "('r1', 'cycle', 'old', datetime('now', '-5 days')), "
                "('r2', 'cycle', 'new', datetime('now')), "
                "('r3', 'daily', 'old', datetime('now', '-5 days'))"
            )
        
        count = mc._cleanup_cycle_reflections(days_old=3)
        assert count == 1 # Only r1 should be deleted
        
        with get_connection(mc.db_path) as conn:
            rows = conn.execute("SELECT id FROM cognitive_reflections").fetchall()
            ids = [r['id'] for r in rows]
            assert 'r1' not in ids
            assert 'r2' in ids
            assert 'r3' in ids

    @patch("zeus_core.core_system.call_cloud_llm")
    def test_summarize_interactions(self, mock_llm, mc):
        mock_llm.return_value = "Resumo semântico consolidado."
        
        with get_connection(mc.db_path) as conn:
            # Insert 5 old interactions (10 days ago, UTC)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            past_date = (now_utc - datetime.timedelta(days=10)).isoformat()
            for i in range(5):
                conn.execute(
                    "INSERT INTO user_interactions (id, type, content, context, hour, weekday, session_id, created_at) "
                    "VALUES (?, ?, ?, '{}', 10, 1, 's1', ?)",
                    (f"i{i}", "chat", f"Mensagem {i}", past_date)
                )
            # Verify count
            rows = conn.execute("SELECT id, created_at FROM user_interactions").fetchall()
            print(f"DEBUG TEST: Found {len(rows)} rows in DB before compression")
            for r in rows:
                print(f"DEBUG TEST: Row {r['id']} created_at: {r['created_at']}")
        
        count = mc._summarize_interactions(days_old=7)
        assert count == 5
        
        with get_connection(mc.db_path) as conn:
            # Check for the summary record
            summary = conn.execute("SELECT * FROM user_interactions WHERE type = 'long_term_summary'").fetchone()
            assert summary is not None
            assert "Resumo semântico" in summary["content"]
            
            # Check that raw records are "archived" (deleted in this simplified implementation)
            raw = conn.execute("SELECT * FROM user_interactions WHERE type = 'chat'").fetchall()
            assert len(raw) == 0
