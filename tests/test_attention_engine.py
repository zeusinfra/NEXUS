"""Tests for the Attention Engine."""
import pytest
from unittest.mock import patch, MagicMock
from zeus_core.cognitive.cognitive_db import init_cognitive_tables
from zeus_core.cognitive.attention_engine import AttentionEngine, AttentionState


@pytest.fixture
def engine(tmp_path):
    db = str(tmp_path / "test_attention.db")
    init_cognitive_tables(db)
    return AttentionEngine(db_path=db)


class TestAttentionEngine:
    @patch("subprocess.check_output")
    def test_get_active_window_vscode(self, mock_cmd, engine):
        # Mock xprop output
        mock_cmd.side_effect = [
            b"window id # 0x12345", # xprop
            b"0x12345  0 1234 zeus MyProject - Visual Studio Code" # wmctrl
        ]
        title = engine._get_active_window_title()
        assert "Visual Studio Code" in title

    @patch("zeus_core.cognitive.attention_engine.AttentionEngine._get_active_window_title")
    @patch("psutil.cpu_percent")
    def test_state_detection_development(self, mock_cpu, mock_title, engine):
        mock_title.return_value = "zeus_core/agent.py - VSCode"
        mock_cpu.return_value = 10.0
        
        snapshot = engine.get_current_attention()
        assert snapshot.state == AttentionState.DEVELOPMENT
        assert snapshot.max_active_goals == 3
        assert snapshot.suggestion_suppression is True

    @patch("zeus_core.cognitive.attention_engine.AttentionEngine._get_active_window_title")
    @patch("psutil.cpu_percent")
    @patch("zeus_core.cognitive.attention_engine.AttentionEngine._is_process_running")
    def test_state_detection_mining(self, mock_proc, mock_cpu, mock_title, engine):
        mock_title.return_value = "Desktop"
        mock_cpu.return_value = 95.0
        mock_proc.return_value = True
        
        snapshot = engine.get_current_attention()
        assert snapshot.state == AttentionState.MINING
        assert snapshot.max_active_goals == 1

    def test_persistence(self, engine):
        engine._persist(engine._build_snapshot(AttentionState.RESEARCH, 0.8, ["Test"], "Chrome"))
        history = engine.get_history()
        assert len(history) >= 1
        assert history[0]["state"] == "research"
