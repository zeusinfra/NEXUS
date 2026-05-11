"""Tests for the cognitive state manager."""

import pytest

from nexus_core.cognitive.cognitive_state import CognitiveStateManager


class TestCognitiveState:
    def test_default_state(self):
        mgr = CognitiveStateManager()
        state = mgr.state
        assert state.mode == "safe"
        assert state.loop_running is False
        assert state.cycle_count == 0
        assert state.health_score == 100

    def test_update(self):
        mgr = CognitiveStateManager()
        mgr.update(health_score=75, current_focus="testing")
        state = mgr.state
        assert state.health_score == 75
        assert state.current_focus == "testing"

    def test_mark_started_stopped(self):
        mgr = CognitiveStateManager()
        mgr.mark_started()
        assert mgr.state.loop_running is True
        assert mgr.state.started_at is not None

        mgr.mark_stopped()
        assert mgr.state.loop_running is False

    def test_mark_cycle_complete(self):
        mgr = CognitiveStateManager()
        mgr.mark_cycle_complete(
            active_goals=3,
            blocked_goals=1,
            pending_confirmations=2,
            focus="test goal",
            health_score=85,
        )
        state = mgr.state
        assert state.cycle_count == 1
        assert state.active_goals == 3
        assert state.blocked_goals == 1
        assert state.pending_confirmations == 2
        assert state.current_focus == "test goal"
        assert state.health_score == 85
        assert state.last_cycle_at is not None

    def test_record_error(self):
        mgr = CognitiveStateManager()
        mgr.record_error()
        mgr.record_error()
        assert mgr.state.error_count == 2

    def test_set_mode_valid(self):
        mgr = CognitiveStateManager()
        mgr.set_mode("autonomous")
        assert mgr.state.mode == "autonomous"

    def test_set_mode_invalid(self):
        mgr = CognitiveStateManager()
        with pytest.raises(ValueError):
            mgr.set_mode("invalid_mode")

    def test_get_snapshot_returns_dict(self):
        mgr = CognitiveStateManager()
        snapshot = mgr.get_snapshot()
        assert isinstance(snapshot, dict)
        assert "mode" in snapshot
        assert "loop_running" in snapshot
        assert "health_score" in snapshot

    def test_state_copy_isolation(self):
        """Modifying the returned state should not affect the manager."""
        mgr = CognitiveStateManager()
        state = mgr.state
        state.health_score = 0
        assert mgr.state.health_score == 100
