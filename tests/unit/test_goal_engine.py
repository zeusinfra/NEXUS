"""Tests for the goal engine."""
import pytest

from zeus_core.cognitive.cognitive_db import init_cognitive_tables
from zeus_core.cognitive.goal_engine import GoalEngine, CognitiveGoal


@pytest.fixture
def engine(tmp_path):
    db = str(tmp_path / "test_goals.db")
    init_cognitive_tables(db)
    return GoalEngine(db_path=db)


class TestGoalEngine:
    def test_create_goal(self, engine):
        goal = engine.create_goal("Test goal", description="A test", goal_type="operational")
        assert goal is not None
        assert goal.title == "Test goal"
        assert goal.status == "pending"
        assert goal.type == "operational"

    def test_create_goal_deduplication(self, engine):
        g1 = engine.create_goal("Unique goal title here")
        g2 = engine.create_goal("Unique goal title here")
        assert g1 is not None
        assert g2 is None  # Deduplicated

    def test_deduplication_case_insensitive(self, engine):
        g1 = engine.create_goal("My Important Goal")
        g2 = engine.create_goal("my important goal")
        assert g1 is not None
        assert g2 is None

    def test_deduplication_substring(self, engine):
        g1 = engine.create_goal("Investigar uso elevado de CPU no servidor principal")
        g2 = engine.create_goal("Investigar uso elevado de CPU no servidor principal extra")
        assert g1 is not None
        assert g2 is None  # Substring match

    def test_security_goal_priority_floor(self, engine):
        goal = engine.create_goal("Security issue", goal_type="security", priority=30)
        assert goal is not None
        assert goal.priority >= 70

    def test_priority_clamped(self, engine):
        goal = engine.create_goal("High priority", priority=200)
        assert goal.priority == 100

    def test_list_goals(self, engine):
        engine.create_goal("Goal A", priority=80)
        engine.create_goal("Goal B", priority=40)
        goals = engine.list_goals()
        assert len(goals) == 2
        assert goals[0].priority >= goals[1].priority  # Ordered by priority desc

    def test_get_active_goals(self, engine):
        engine.create_goal("Active 1")
        engine.create_goal("Active 2")
        g3 = engine.create_goal("Done goal")
        engine.update_status(g3.id, "done")

        active = engine.get_active_goals()
        assert len(active) == 2

    def test_update_status(self, engine):
        goal = engine.create_goal("Status test")
        engine.update_status(goal.id, "executing")
        updated = engine.get_goal(goal.id)
        assert updated.status == "executing"

    def test_update_status_invalid(self, engine):
        goal = engine.create_goal("Invalid status")
        result = engine.update_status(goal.id, "nonexistent_status")
        assert result is False

    def test_link_plan(self, engine):
        goal = engine.create_goal("Plan link test")
        engine.link_plan(goal.id, "plan_abc")
        updated = engine.get_goal(goal.id)
        assert updated.plan_id == "plan_abc"
        assert updated.status == "planned"

    def test_adjust_priority(self, engine):
        goal = engine.create_goal("Priority adjust", priority=50)
        engine.adjust_priority(goal.id, -20)
        updated = engine.get_goal(goal.id)
        assert updated.priority == 30

    def test_count_by_status(self, engine):
        engine.create_goal("Pending 1")
        engine.create_goal("Pending 2")
        g3 = engine.create_goal("Done")
        engine.update_status(g3.id, "done")

        counts = engine.count_by_status()
        assert counts.get("pending", 0) == 2
        assert counts.get("done", 0) == 1

    def test_invalid_type_defaults(self, engine):
        goal = engine.create_goal("Invalid type", goal_type="nonexistent")
        assert goal.type == "operational"
