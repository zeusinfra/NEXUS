"""Tests for the cognitive learning engine."""

import pytest

from nexus_core.cognitive.cognitive_db import init_cognitive_tables
from nexus_core.cognitive.learning_engine import CognitiveLearningEngine


@pytest.fixture
def engine(tmp_path):
    db = str(tmp_path / "test_learning.db")
    init_cognitive_tables(db)
    return CognitiveLearningEngine(db_path=db)


class TestCognitiveLearningEngine:
    def test_store_lesson(self, engine):
        lesson = engine.store_lesson(
            "Ollama precisa estar ativo para provider funcionar",
            source="failure",
            confidence=0.8,
            tags=["llm", "ollama"],
        )
        assert lesson.id is not None
        assert lesson.source == "failure"
        assert lesson.confidence == 0.8
        assert "ollama" in lesson.tags

    def test_list_lessons(self, engine):
        engine.store_lesson("Lesson A", source="execution")
        engine.store_lesson("Lesson B", source="failure")
        engine.store_lesson("Lesson C", source="execution")

        all_lessons = engine.list_lessons()
        assert len(all_lessons) == 3

        failures = engine.list_lessons(source="failure")
        assert len(failures) == 1

    def test_confidence_clamped(self, engine):
        lesson = engine.store_lesson("Too confident", confidence=1.5)
        assert lesson.confidence == 1.0

        lesson2 = engine.store_lesson("Negative confidence", confidence=-0.5)
        assert lesson2.confidence == 0.0

    def test_learn_from_successful_result(self, engine):
        goal = {"id": "g1", "title": "Test goal", "type": "operational"}
        plan = {"id": "p1"}
        results = [
            {"status": "success", "error": ""},
            {"status": "success", "error": ""},
        ]
        lesson = engine.learn_from_result(goal, plan, results)
        assert lesson is not None
        assert "sucesso total" in lesson.lesson
        assert lesson.confidence == 0.9

    def test_learn_from_failed_result(self, engine):
        goal = {"id": "g2", "title": "Failing goal", "type": "performance"}
        plan = {"id": "p2"}
        results = [
            {"status": "success", "error": ""},
            {"status": "failed", "error": "Connection refused"},
        ]
        lesson = engine.learn_from_result(goal, plan, results)
        assert lesson is not None
        assert "falha" in lesson.lesson.lower()
        assert "Connection refused" in lesson.lesson

    def test_learn_from_blocked_result(self, engine):
        goal = {"id": "g3", "title": "Blocked goal", "type": "security"}
        plan = {"id": "p3"}
        results = [
            {"status": "blocked", "error": "Policy violation"},
        ]
        lesson = engine.learn_from_result(goal, plan, results)
        assert lesson is not None
        assert "bloqueada" in lesson.lesson.lower()

    def test_learn_from_empty_results(self, engine):
        goal = {"id": "g4", "title": "Empty", "type": "operational"}
        plan = {"id": "p4"}
        lesson = engine.learn_from_result(goal, plan, [])
        assert lesson is None

    def test_update_goal_priority_success(self, engine):
        goal = {"id": "g1"}
        results = [
            {"status": "success"},
            {"status": "success"},
        ]
        delta = engine.update_goal_priority(goal, results)
        assert delta == -10  # Reduce priority (goal handled)

    def test_update_goal_priority_failure(self, engine):
        goal = {"id": "g2"}
        results = [
            {"status": "failed"},
            {"status": "failed"},
        ]
        delta = engine.update_goal_priority(goal, results)
        assert delta == 5  # Increase priority (needs investigation)

    def test_detect_repeated_failures(self, engine):
        # Store the same failure lesson 3 times
        for _ in range(3):
            engine.store_lesson("Provider timeout on port 11434", source="failure")

        failures = engine.detect_repeated_failures(threshold=3)
        assert len(failures) >= 1
        assert failures[0]["count"] >= 3

    def test_detect_no_repeated_failures(self, engine):
        engine.store_lesson("Unique failure 1", source="failure")
        engine.store_lesson("Unique failure 2", source="failure")
        failures = engine.detect_repeated_failures(threshold=3)
        assert len(failures) == 0
