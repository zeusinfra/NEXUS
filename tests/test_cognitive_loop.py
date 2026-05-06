"""Tests for the cognitive loop — single cycle execution."""
import asyncio
import pytest

from zeus_core.cognitive.cognitive_db import init_cognitive_tables
from zeus_core.cognitive.cognitive_loop import CognitiveLoop
from zeus_core.cognitive.cognitive_state import cognitive_state_manager


@pytest.fixture
def loop_instance(tmp_path):
    db = str(tmp_path / "test_loop.db")
    init_cognitive_tables(db)
    return CognitiveLoop(db_path=db)


class TestCognitiveLoop:
    @pytest.mark.asyncio
    async def test_single_cycle_runs_without_crash(self, loop_instance):
        """The loop should complete one cycle without raising exceptions."""
        await loop_instance.run_single_cycle()
        # After a cycle, the cognitive state should be updated
        state = cognitive_state_manager.state
        assert state.cycle_count >= 1

    @pytest.mark.asyncio
    async def test_start_and_stop(self, loop_instance):
        """The loop should start and stop cleanly."""
        task = asyncio.create_task(loop_instance.start())
        # Let it run briefly
        await asyncio.sleep(0.5)
        assert loop_instance.is_running is True

        await loop_instance.stop()
        await asyncio.wait_for(task, timeout=5)
        assert loop_instance.is_running is False

    @pytest.mark.asyncio
    async def test_perception_returns_dict(self, loop_instance):
        perception = loop_instance._perceive()
        assert isinstance(perception, dict)
        assert "timestamp" in perception
        assert "system" in perception
        assert "summary" in perception

    @pytest.mark.asyncio
    async def test_analysis_returns_dict(self, loop_instance):
        perception = loop_instance._perceive()
        memory_update = loop_instance._update_memory(perception)
        analysis = loop_instance._analyze(perception, memory_update)
        assert isinstance(analysis, dict)
        assert "patterns" in analysis
        assert "anomalies" in analysis
        assert "importance_score" in analysis

    @pytest.mark.asyncio
    async def test_health_calculation(self, loop_instance):
        perception = {"system": {"cpu_percent": 50, "ram_percent": 60, "disk_percent": 50}}
        analysis = {"anomalies": []}
        health = loop_instance._calculate_health(perception, analysis)
        assert 80 <= health <= 100

    @pytest.mark.asyncio
    async def test_health_calculation_under_pressure(self, loop_instance):
        perception = {"system": {"cpu_percent": 95, "ram_percent": 92, "disk_percent": 50}}
        analysis = {"anomalies": [{"type": "high_cpu"}, {"type": "high_ram"}]}
        health = loop_instance._calculate_health(perception, analysis)
        assert health < 60
