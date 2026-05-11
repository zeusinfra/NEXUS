"""Tests for the reflection engine."""

import pytest

from zeus_core.cognitive.cognitive_db import init_cognitive_tables
from zeus_core.cognitive.reflection_engine import ReflectionEngine


@pytest.fixture
def engine(tmp_path):
    db = str(tmp_path / "test_reflections.db")
    init_cognitive_tables(db)
    return ReflectionEngine(db_path=db)


class TestReflectionEngine:
    def test_cycle_reflection(self, engine):
        ref = engine.cycle_reflection(
            cycle_id="test-001",
            perception_summary="Sistema estável",
            analysis_summary="Sem anomalias",
            goals_created=2,
            actions_executed=3,
        )
        assert ref.type == "cycle"
        assert "Sistema estável" in ref.summary
        assert ref.cycle_id == "test-001"

    def test_daily_reflection(self, engine):
        ref = engine.daily_reflection(
            events_summary=["Backup executado", "Log rotacionado"],
            failures=["Provider timeout"],
            opportunities=["Otimizar cache"],
            lessons_learned=["Ollama precisa estar ativo"],
            suggested_goals=["Criar alerta de timeout"],
            cycle_count=42,
            health_score=90,
        )
        assert ref.type == "daily"
        assert "42" in ref.summary
        assert len(ref.events) == 2
        assert len(ref.failures) == 1

    def test_failure_reflection(self, engine):
        ref = engine.failure_reflection(
            error="Connection refused on port 11434",
            context="Trying to reach Ollama",
            goal_id="goal-123",
        )
        assert ref.type == "failure"
        assert "Connection refused" in ref.summary

    def test_improvement_reflection(self, engine):
        ref = engine.improvement_reflection(
            opportunities=["Consolidar logs"],
            suggestions=["Implementar rotação automática"],
        )
        assert ref.type == "improvement"
        assert len(ref.opportunities) == 1

    def test_list_reflections(self, engine):
        engine.cycle_reflection(cycle_id="c1")
        engine.cycle_reflection(cycle_id="c2")
        engine.daily_reflection()

        all_refs = engine.list_reflections()
        assert len(all_refs) == 3

        cycles = engine.list_reflections(reflection_type="cycle")
        assert len(cycles) == 2

        dailies = engine.list_reflections(reflection_type="daily")
        assert len(dailies) == 1

    def test_get_last_daily(self, engine):
        engine.daily_reflection(cycle_count=10, health_score=80)
        last = engine.get_last_daily()
        assert last is not None
        assert last.type == "daily"

    def test_reflection_persisted(self, engine):
        ref = engine.cycle_reflection(cycle_id="persist-test")
        all_refs = engine.list_reflections()
        ids = [r.id for r in all_refs]
        assert ref.id in ids

    def test_render_markdown(self, engine):
        ref = engine.daily_reflection(
            events_summary=["Event 1"],
            failures=["Failure 1"],
            opportunities=["Opportunity 1"],
            suggested_goals=["Goal 1"],
            lessons_learned=["Lesson 1"],
        )
        md = engine._render_markdown(ref, "2026-01-01")
        assert "# ZEUS Reflection" in md
        assert "## Resumo" in md
        assert "## Falhas" in md
        assert "Failure 1" in md
