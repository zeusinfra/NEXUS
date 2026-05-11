"""Tests for the User Profile Engine."""

import pytest
from datetime import datetime, timedelta
from nexus_core.cognitive.cognitive_db import init_cognitive_tables
from nexus_core.cognitive.user_profile_engine import (
    UserProfileEngine,
    record_interaction,
)


@pytest.fixture
def engine(tmp_path):
    db = str(tmp_path / "test_profile.db")
    init_cognitive_tables(db)
    return UserProfileEngine(db_path=db)


class TestUserProfileEngine:
    def test_record_interaction(self, engine):
        db = engine.db_path
        iid = record_interaction("chat", "Hello Zeus", "direct", db_path=db)
        assert iid is not None

        stats = engine.get_interaction_stats()
        assert stats["total_interactions"] == 1
        assert stats["by_type"]["chat"] == 1

    def test_session_resolution(self, engine):
        db = engine.db_path
        # First interaction creates session
        iid1 = record_interaction("chat", "Msg 1", db_path=db)
        # Get session_id
        from nexus_core.cognitive.cognitive_db import get_connection

        with get_connection(db) as conn:
            s1 = conn.execute(
                "SELECT session_id FROM user_interactions WHERE id=?", (iid1,)
            ).fetchone()[0]

        # Second interaction within gap should reuse session
        iid2 = record_interaction("command", "ls", db_path=db)
        with get_connection(db) as conn:
            s2 = conn.execute(
                "SELECT session_id FROM user_interactions WHERE id=?", (iid2,)
            ).fetchone()[0]

        assert s1 == s2

    def test_temporal_context_building(self, engine):
        ctx = engine.build_temporal_context()
        assert ctx.current_hour >= 0
        assert ctx.current_hour < 24
        assert ctx.period_label in [
            "morning",
            "afternoon_early",
            "afternoon",
            "evening",
            "night",
            "late_night",
        ]

    def test_habit_synthesis(self, engine):
        db = engine.db_path
        # Record several interactions at same hour
        for i in range(5):
            record_interaction("chat", f"Msg {i}", db_path=db)

        habits = engine.synthesize_habits()
        assert len(habits) >= 1
        assert "chat" in habits[0].name
        assert habits[0].confidence > 0

    def test_workflow_detection(self, engine):
        db = engine.db_path
        # Record a repeated sequence in different sessions
        # Session 1
        record_interaction("chat", "start", db_path=db)
        record_interaction("command", "run", db_path=db)
        record_interaction("file_access", "save", db_path=db)

        # Force new session by waiting? No, let's just wait or mock it.
        # Actually session gap is 5 mins. I'll mock the timestamp or just use different sessions if I can.
        # record_interaction doesn't take session_id, it resolves it.
        # I'll just insert directly to create a second session.
        from nexus_core.cognitive.cognitive_db import get_connection

        now = datetime.now()
        old = (now - timedelta(minutes=10)).isoformat()
        with get_connection(db) as conn:
            conn.execute(
                "INSERT INTO user_interactions (id, type, hour, weekday, session_id, created_at) VALUES (?,?,?,?,?,?)",
                ("i1", "chat", now.hour, now.weekday(), "s2", old),
            )
            conn.execute(
                "INSERT INTO user_interactions (id, type, hour, weekday, session_id, created_at) VALUES (?,?,?,?,?,?)",
                ("i2", "command", now.hour, now.weekday(), "s2", old),
            )
            conn.execute(
                "INSERT INTO user_interactions (id, type, hour, weekday, session_id, created_at) VALUES (?,?,?,?,?,?)",
                ("i3", "file_access", now.hour, now.weekday(), "s2", old),
            )

        workflows = engine.detect_workflows()
        assert len(workflows) >= 1
        assert "chat" in workflows[0].steps[0]

    def test_profile_summary(self, engine):
        summary = engine.get_profile_summary()
        assert "temporal" in summary
        assert "session" in summary
        assert "habits" in summary
        assert "workflows" in summary
