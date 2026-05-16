from __future__ import annotations

import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


STOPWORDS = {
    "a",
    "o",
    "e",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "um",
    "uma",
    "para",
    "por",
    "com",
    "que",
    "em",
    "no",
    "na",
    "os",
    "as",
    "me",
    "eu",
    "voce",
    "você",
    "isso",
    "esse",
    "essa",
    "aquele",
    "aquela",
    "como",
    "mais",
    "menos",
}


@dataclass(frozen=True)
class ConversationMemoryItem:
    role: str
    content: str
    created_at: float
    score: float = 0.0


class SQLiteConversationMemory:
    """Small persistent memory for chat turns and lightweight lexical recall."""

    def __init__(self, db_path: str | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.db_path = db_path or os.getenv(
            "NEXUS_CONVERSATION_DB_PATH",
            str(root / "data" / "conversation_memory.db"),
        )
        assert self.db_path is not None
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        assert self.db_path is not None
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_session_time "
                "ON conversation_turns(session_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_client_time "
                "ON conversation_turns(client_id, created_at)"
            )

    def add_turn(
        self, session_id: str, client_id: str, role: str, content: str
    ) -> None:
        content = (content or "").strip()
        if not content:
            return
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversation_turns(session_id, client_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, client_id, role, content[:12000], time.time()),
            )

    def recent_turns(
        self, session_id: str, *, limit: int = 8
    ) -> list[ConversationMemoryItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM conversation_turns "
                "WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            ConversationMemoryItem(row["role"], row["content"], row["created_at"])
            for row in reversed(rows)
        ]

    def recall_similar(
        self,
        query: str,
        *,
        client_id: str,
        limit: int = 6,
        scan_limit: int = 160,
    ) -> list[ConversationMemoryItem]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM conversation_turns "
                "WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
                (client_id, scan_limit),
            ).fetchall()

        scored: list[ConversationMemoryItem] = []
        for row in rows:
            tokens = self._tokens(row["content"])
            if not tokens:
                continue
            overlap = len(query_tokens & tokens)
            if overlap <= 0:
                continue
            score = overlap / max(1, len(query_tokens))
            scored.append(
                ConversationMemoryItem(
                    row["role"], row["content"], row["created_at"], score
                )
            )
        scored.sort(key=lambda item: (item.score, item.created_at), reverse=True)
        return scored[:limit]

    def build_context_block(
        self, query: str, *, session_id: str, client_id: str
    ) -> str:
        parts: list[str] = []
        recent = self.recent_turns(session_id, limit=8)
        if recent:
            lines = [f"{item.role.upper()}: {item.content[:900]}" for item in recent]
            parts.append("--- HISTORICO RECENTE DA CONVERSA ---\n" + "\n".join(lines))

        similar = self.recall_similar(query, client_id=client_id, limit=6)
        if similar:
            lines = [
                f"{item.role.upper()} [{item.score:.2f}]: {item.content[:700]}"
                for item in similar
            ]
            parts.append("--- MEMORIAS DE CONVERSAS PARECIDAS ---\n" + "\n".join(lines))

        return "\n\n".join(parts)

    @staticmethod
    def _tokens(text: str) -> set[str]:
        raw = re.findall(r"[A-Za-zÀ-ÿ0-9_]{3,}", (text or "").lower())
        return {token for token in raw if token not in STOPWORDS}


conversation_memory = SQLiteConversationMemory()
