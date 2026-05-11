"""
ZEUS Cognitive Core — Attention Engine.

Determines the system's "Attention State" by analyzing user activity,
active windows, and system pressure.
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum

import psutil
from nexus_core.cognitive.cognitive_db import get_connection
from nexus_core.observability import get_logger, log_event

logger = get_logger("zeus.cognitive.attention")

# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------


class AttentionState(str, Enum):
    IDLE = "idle"
    DEVELOPMENT = "development"
    DEBUGGING = "debugging"
    DEEP_FOCUS = "deep_focus"
    MINING = "mining"
    RESEARCH = "research"
    SECURITY_ALERT = "security_alert"
    MAINTENANCE = "maintenance"
    REFLECTION = "reflection"
    LOW_ENERGY = "low_energy"


@dataclass
class AttentionSnapshot:
    state: AttentionState
    confidence: float
    priority_bias: dict[str, float] = field(
        default_factory=lambda: {"performance": 1.0, "security": 1.0, "reflection": 1.0}
    )
    interruptions_allowed: bool = True
    max_active_goals: int = 5
    suggestion_suppression: bool = False
    reflection_mode: str = "normal"
    triggers: list[str] = field(default_factory=list)
    active_window: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d


# ------------------------------------------------------------------
# Attention Engine Logic
# ------------------------------------------------------------------


class AttentionEngine:
    """The central engine for focus and behavior modulation."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self._last_state: AttentionState = AttentionState.IDLE

    def get_current_attention(self) -> AttentionSnapshot:
        """Analyze current environment and return an attention snapshot."""
        triggers = []

        # 1. System Inputs
        cpu = psutil.cpu_percent(interval=None)
        active_window = self._get_active_window_title()

        # 2. Rule Evaluation
        state = AttentionState.IDLE
        confidence = 0.5

        # Check for Security Alert (High Priority)
        # (Could be expanded to check for specific logs or security flags)

        # Check for Mining
        if cpu > 80 and self._is_process_running(["xmrig", "miner", "ethminer"]):
            state = AttentionState.MINING
            confidence = 0.95
            triggers.append("High CPU + miner process detected")

        # Check for Development
        elif active_window and any(
            x in active_window.lower()
            for x in [
                "vscode",
                "visual studio",
                "intellij",
                "pycharm",
                "sublime",
                "neovim",
            ]
        ):
            state = AttentionState.DEVELOPMENT
            confidence = 0.9
            triggers.append(f"Development window active: {active_window}")
            if "debug" in active_window.lower():
                state = AttentionState.DEBUGGING
                triggers.append("Debugging context detected in window title")

        # Check for Research
        elif active_window and any(
            x in active_window.lower()
            for x in ["chrome", "brave", "firefox", "arxiv", "paper", "documentation"]
        ):
            state = AttentionState.RESEARCH
            confidence = 0.7
            triggers.append(f"Research window active: {active_window}")

        # Check for Deep Focus (Long session, stable window)
        # (For now, let's keep it simple: if session is long and active window is work-related)

        # 3. Behavior Modulation
        snapshot = self._build_snapshot(state, confidence, triggers, active_window)

        # 4. Persistence & Logging
        if state != self._last_state:
            self._persist(snapshot)
            self._last_state = state
            log_event(
                logger,
                20,
                "attention_state_changed",
                state=state.value,
                triggers=triggers,
            )

        return snapshot

    def _build_snapshot(
        self,
        state: AttentionState,
        confidence: float,
        triggers: list[str],
        active_window: str | None,
    ) -> AttentionSnapshot:
        # Default modulation
        bias = {"performance": 1.0, "security": 1.0, "reflection": 1.0}
        interruptions = True
        max_goals = 5
        suppress = False
        rmode = "normal"

        if state == AttentionState.DEVELOPMENT:
            bias = {"performance": 1.2, "security": 1.1, "reflection": 0.5}
            max_goals = 3
            suppress = True  # Suppress non-critical to avoid annoyance
        elif state == AttentionState.DEBUGGING:
            bias = {"performance": 0.8, "security": 1.0, "reflection": 1.5}
            max_goals = 2
            interruptions = False
        elif state == AttentionState.DEEP_FOCUS:
            bias = {"performance": 1.5, "security": 1.2, "reflection": 0.2}
            interruptions = False
            suppress = True
            rmode = "minimal"
        elif state == AttentionState.MINING:
            bias = {"performance": 0.5, "security": 1.5, "reflection": 0.3}
            max_goals = 1
        elif state == AttentionState.IDLE:
            rmode = "deep"  # Allow deep reflection when idle

        return AttentionSnapshot(
            state=state,
            confidence=confidence,
            priority_bias=bias,
            interruptions_allowed=interruptions,
            max_active_goals=max_goals,
            suggestion_suppression=suppress,
            reflection_mode=rmode,
            triggers=triggers,
            active_window=active_window,
        )

    def _get_active_window_title(self) -> str | None:
        """Get the title of the currently focused window on Linux."""
        try:
            # 1. Get active window ID
            out_id = subprocess.check_output(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"], stderr=subprocess.DEVNULL
            ).decode()
            match = re.search(r"window id # (0x[0-9a-f]+)", out_id)
            if not match:
                return None
            win_id = match.group(1)

            # 2. Get window details using wmctrl
            out_list = subprocess.check_output(
                ["wmctrl", "-lp"], stderr=subprocess.DEVNULL
            ).decode()
            for line in out_list.splitlines():
                if win_id.lower() in line.lower():
                    # Format: 0x04600004  0 707095 zeus TITLE...
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        return parts[4]
            return None
        except Exception:
            return None

    def _is_process_running(self, keywords: list[str]) -> bool:
        """Check if any process matching keywords is running."""
        try:
            for proc in psutil.process_iter(["name"]):
                if any(k in (proc.info["name"] or "").lower() for k in keywords):
                    return True
        except Exception:
            pass
        return False

    def _persist(self, s: AttentionSnapshot) -> None:
        aid = uuid.uuid4().hex[:12]
        try:
            with get_connection(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO cognitive_attention_history (id, state, confidence, triggers, metadata, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        aid,
                        s.state.value,
                        s.confidence,
                        json.dumps(s.triggers),
                        json.dumps({"active_window": s.active_window}),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except Exception:
            pass

    def get_history(self, limit: int = 50) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM cognitive_attention_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
