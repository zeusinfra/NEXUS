"""Tests for the cognitive database layer."""

import pytest

from zeus_core.cognitive.cognitive_db import get_connection, init_cognitive_tables


@pytest.fixture
def tmp_db(tmp_path):
    db = str(tmp_path / "test_cognitive.db")
    init_cognitive_tables(db)
    return db


class TestCognitiveDB:
    def test_tables_created(self, tmp_db):
        with get_connection(tmp_db) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
        assert "cognitive_goals" in tables
        assert "cognitive_reflections" in tables
        assert "cognitive_actions" in tables
        assert "cognitive_lessons" in tables

    def test_idempotent_init(self, tmp_db):
        """Calling init_cognitive_tables twice should not raise."""
        init_cognitive_tables(tmp_db)
        init_cognitive_tables(tmp_db)

    def test_context_manager_commits(self, tmp_db):
        with get_connection(tmp_db) as conn:
            conn.execute(
                "INSERT INTO cognitive_lessons (id, lesson, source, confidence, tags, created_at) "
                "VALUES ('test1', 'lesson text', 'test', 0.5, '[]', '2026-01-01T00:00:00Z')"
            )
        with get_connection(tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_lessons WHERE id = 'test1'"
            ).fetchone()
        assert row is not None
        assert row["lesson"] == "lesson text"

    def test_context_manager_rollback_on_error(self, tmp_db):
        try:
            with get_connection(tmp_db) as conn:
                conn.execute(
                    "INSERT INTO cognitive_lessons (id, lesson, source, confidence, tags, created_at) "
                    "VALUES ('test2', 'will rollback', 'test', 0.5, '[]', '2026-01-01T00:00:00Z')"
                )
                raise ValueError("force rollback")
        except ValueError:
            pass

        with get_connection(tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_lessons WHERE id = 'test2'"
            ).fetchone()
        assert row is None

    def test_indexes_created(self, tmp_db):
        with get_connection(tmp_db) as conn:
            indexes = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            ]
        assert "idx_goals_status" in indexes
        assert "idx_goals_priority" in indexes
        assert "idx_actions_status" in indexes
