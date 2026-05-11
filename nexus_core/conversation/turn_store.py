import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Turn:
    turn_id: str
    session_id: str
    parent_turn_id: Optional[str]
    timestamp: str
    role: str
    topic_id: str
    intent: str
    content: str
    content_hash: str
    source: str
    importance: float
    expires_at: Optional[str]

    @classmethod
    def create(
        cls,
        session_id: str,
        role: str,
        content: str,
        source: str = "chat",
        topic_id: str = "general",
        intent: str = "unknown",
        parent_turn_id: Optional[str] = None,
        importance: float = 1.0,
    ) -> "Turn":
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(
            turn_id=uuid.uuid4().hex,
            session_id=session_id,
            parent_turn_id=parent_turn_id,
            timestamp=datetime.now().isoformat(),
            role=role,
            topic_id=topic_id,
            intent=intent,
            content=content,
            content_hash=content_hash,
            source=source,
            importance=importance,
            expires_at=None,
        )


class TurnStore:
    """Armazena e gerencia os turnos da conversa, evitando duplicação e concatenação bruta."""

    def __init__(self):
        # In a real scenario this should use a DB like SQLite. Using in-memory for the architectural base.
        self._turns: Dict[str, Turn] = {}
        self._session_turns: Dict[str, List[str]] = {}

    def add_turn(self, turn: Turn) -> None:
        # Anti-concat: Check for duplication in the same session
        if turn.session_id in self._session_turns:
            for existing_id in self._session_turns[turn.session_id]:
                existing_turn = self._turns[existing_id]
                if (
                    existing_turn.content_hash == turn.content_hash
                    and existing_turn.role == turn.role
                ):
                    # Duplicated content, ignore or update timestamp
                    return

        self._turns[turn.turn_id] = turn
        if turn.session_id not in self._session_turns:
            self._session_turns[turn.session_id] = []
        self._session_turns[turn.session_id].append(turn.turn_id)

    def get_turns_for_session(self, session_id: str) -> List[Turn]:
        turn_ids = self._session_turns.get(session_id, [])
        return [self._turns[tid] for tid in turn_ids]

    def get_turns_for_topic(self, session_id: str, topic_id: str) -> List[Turn]:
        turns = self.get_turns_for_session(session_id)
        return [t for t in turns if t.topic_id == topic_id]


turn_store = TurnStore()
