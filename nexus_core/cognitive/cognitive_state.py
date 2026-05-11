"""
ZEUS Cognitive Core — Global Cognitive State.

Thread-safe singleton holding the current cognitive state of the system.
Updated atomically after each loop cycle and exposed via API.
"""

from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CognitiveState:
    """Represents the current cognitive state of ZEUS."""

    mode: str = "safe"  # safe | autonomous | manual
    loop_running: bool = False
    last_cycle_at: str | None = None
    current_focus: str | None = None
    active_goals: int = 0
    blocked_goals: int = 0
    pending_confirmations: int = 0
    last_reflection: str | None = None
    health_score: int = 100
    cycle_count: int = 0
    started_at: str | None = None
    error_count: int = 0

    # 🧠 Cognitive Maturity Pillars (v3.1)
    attention: dict = field(
        default_factory=lambda: {"state": "idle", "focus_score": 0.0}
    )
    active_goals_list: list = field(default_factory=list)
    privacy_status: dict = field(
        default_factory=lambda: {"shield": "active", "masked_count": 0}
    )

    def to_dict(self) -> dict:
        return asdict(self)


class CognitiveStateManager:
    """Thread-safe manager for the global cognitive state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        mode = os.getenv("NEXUS_COGNITIVE_LOOP_MODE", "safe").strip().lower()
        if mode not in {"safe", "autonomous", "manual"}:
            mode = "safe"
        self._state = CognitiveState(mode=mode)

    @property
    def state(self) -> CognitiveState:
        with self._lock:
            # Return a copy to avoid race conditions on reads
            return CognitiveState(**asdict(self._state))

    def update(self, **kwargs) -> None:
        """Update one or more fields atomically."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)

    def mark_cycle_complete(
        self,
        *,
        active_goals: int = 0,
        blocked_goals: int = 0,
        pending_confirmations: int = 0,
        focus: str | None = None,
        health_score: int = 100,
        attention: dict | None = None,
        active_goals_list: list | None = None,
        privacy_status: dict | None = None,
    ) -> None:
        """Called at the end of each cognitive loop cycle."""
        with self._lock:
            self._state.last_cycle_at = _now_iso()
            self._state.cycle_count += 1
            self._state.active_goals = active_goals
            self._state.blocked_goals = blocked_goals
            self._state.pending_confirmations = pending_confirmations
            self._state.current_focus = focus
            self._state.health_score = health_score
            if attention:
                self._state.attention = attention
            if active_goals_list is not None:
                self._state.active_goals_list = active_goals_list
            if privacy_status:
                self._state.privacy_status = privacy_status

    def mark_started(self) -> None:
        with self._lock:
            self._state.loop_running = True
            self._state.started_at = _now_iso()

    def mark_stopped(self) -> None:
        with self._lock:
            self._state.loop_running = False

    def record_error(self) -> None:
        with self._lock:
            self._state.error_count += 1

    def set_mode(self, mode: str) -> None:
        if mode not in {"safe", "autonomous", "manual"}:
            raise ValueError(f"Invalid cognitive mode: {mode}")
        with self._lock:
            self._state.mode = mode

    def get_snapshot(self) -> dict:
        """Return a JSON-safe dict of the current state."""
        return self.state.to_dict()


# Module-level singleton
cognitive_state_manager = CognitiveStateManager()
