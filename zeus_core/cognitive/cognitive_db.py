"""
ZEUS Cognitive Core — Database Layer.

Manages the cognitive tables inside the shared zeus_events.db:
  - cognitive_goals
  - cognitive_reflections
  - cognitive_actions
  - cognitive_lessons
  - user_interactions
  - user_habits
  - user_workflows
  - privacy_consents
  - privacy_audit_log
  - cognitive_attention_history

All tables are created lazily via ``init_cognitive_tables()``.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("ZEUS_DB_PATH", "./zeus_events.db")


@contextmanager
def get_connection(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Yield an auto-committing SQLite connection."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_cognitive_tables(db_path: str | None = None) -> None:
    """Create cognitive tables if they don't exist yet."""
    with get_connection(db_path) as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS cognitive_goals (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                type        TEXT NOT NULL DEFAULT 'operational',
                origin      TEXT NOT NULL DEFAULT 'system_analysis',
                priority    INTEGER NOT NULL DEFAULT 50,
                risk        TEXT NOT NULL DEFAULT 'low',
                status      TEXT NOT NULL DEFAULT 'pending',
                evidence    TEXT NOT NULL DEFAULT '[]',
                plan_id     TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS cognitive_reflections (
                id          TEXT PRIMARY KEY,
                type        TEXT NOT NULL DEFAULT 'cycle',
                summary     TEXT NOT NULL DEFAULT '',
                events      TEXT NOT NULL DEFAULT '[]',
                failures    TEXT NOT NULL DEFAULT '[]',
                opportunities TEXT NOT NULL DEFAULT '[]',
                actions     TEXT NOT NULL DEFAULT '[]',
                learning    TEXT NOT NULL DEFAULT '',
                next_goals  TEXT NOT NULL DEFAULT '[]',
                cycle_id    TEXT,
                created_at  TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS cognitive_actions (
                id          TEXT PRIMARY KEY,
                plan_id     TEXT,
                step_index  INTEGER NOT NULL DEFAULT 0,
                action_type TEXT NOT NULL DEFAULT 'read',
                description TEXT NOT NULL DEFAULT '',
                command     TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                output      TEXT NOT NULL DEFAULT '',
                error       TEXT NOT NULL DEFAULT '',
                risk        TEXT NOT NULL DEFAULT 'low',
                created_at  TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS cognitive_lessons (
                id          TEXT PRIMARY KEY,
                lesson      TEXT NOT NULL,
                source      TEXT NOT NULL DEFAULT 'execution',
                confidence  REAL NOT NULL DEFAULT 0.5,
                tags        TEXT NOT NULL DEFAULT '[]',
                created_at  TEXT NOT NULL
            )
        """)

        # --- User Profile Intelligence tables ---

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_interactions (
                id          TEXT PRIMARY KEY,
                type        TEXT NOT NULL,
                content     TEXT NOT NULL DEFAULT '',
                context     TEXT NOT NULL DEFAULT '',
                hour        INTEGER NOT NULL,
                weekday     INTEGER NOT NULL,
                session_id  TEXT,
                created_at  TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_habits (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                time_range      TEXT NOT NULL,
                weekdays        TEXT NOT NULL DEFAULT '[0,1,2,3,4]',
                avg_duration_m  REAL NOT NULL DEFAULT 0,
                frequency       TEXT NOT NULL DEFAULT 'daily',
                tools           TEXT NOT NULL DEFAULT '[]',
                topics          TEXT NOT NULL DEFAULT '[]',
                confidence      REAL NOT NULL DEFAULT 0.5,
                last_observed   TEXT NOT NULL,
                created_at      TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_workflows (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                description     TEXT NOT NULL DEFAULT '',
                steps           TEXT NOT NULL DEFAULT '[]',
                trigger         TEXT NOT NULL DEFAULT '',
                frequency       TEXT NOT NULL DEFAULT 'daily',
                avg_duration_m  REAL NOT NULL DEFAULT 0,
                confidence      REAL NOT NULL DEFAULT 0.5,
                last_observed   TEXT NOT NULL,
                created_at      TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS privacy_consents (
                id          TEXT PRIMARY KEY,
                resource    TEXT NOT NULL,
                scope       TEXT NOT NULL DEFAULT 'session',
                allowed     BOOLEAN NOT NULL DEFAULT 0,
                expires_at  TEXT,
                created_at  TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS privacy_audit_log (
                id          TEXT PRIMARY KEY,
                event_type  TEXT NOT NULL,
                resource    TEXT NOT NULL,
                destination TEXT NOT NULL,
                action      TEXT NOT NULL,
                reason      TEXT,
                metadata    TEXT NOT NULL DEFAULT '{}',
                created_at  TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS cognitive_attention_history (
                id          TEXT PRIMARY KEY,
                state       TEXT NOT NULL,
                confidence  REAL NOT NULL,
                triggers    TEXT NOT NULL,
                metadata    TEXT NOT NULL DEFAULT '{}',
                created_at  TEXT NOT NULL
            )
        """)

        # Indexes for common query patterns
        c.execute("CREATE INDEX IF NOT EXISTS idx_goals_status ON cognitive_goals(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_goals_priority ON cognitive_goals(priority DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reflections_type ON cognitive_reflections(type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON cognitive_actions(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_actions_plan ON cognitive_actions(plan_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lessons_source ON cognitive_lessons(source)")

        # User profile indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_interactions_type ON user_interactions(type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_interactions_hour ON user_interactions(hour)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_interactions_created ON user_interactions(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_interactions_session ON user_interactions(session_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_habits_name ON user_habits(name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_workflows_name ON user_workflows(name)")

        # Privacy indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_consents_resource ON privacy_consents(resource)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_privacy_audit_event ON privacy_audit_log(event_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_privacy_audit_created ON privacy_audit_log(created_at)")

        # Attention indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_attention_state ON cognitive_attention_history(state)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_attention_created ON cognitive_attention_history(created_at)")


# Auto-initialize on import
init_cognitive_tables()

