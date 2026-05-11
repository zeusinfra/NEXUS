"""Tests for the cognitive planner."""

import pytest

from nexus_core.cognitive.planner import CognitivePlanner, CognitivePlan, PlanStep


@pytest.fixture
def planner():
    return CognitivePlanner()


class TestCognitivePlanner:
    def test_create_plan_returns_plan(self, planner):
        goal = {
            "id": "goal-1",
            "title": "Investigar uso de CPU",
            "description": "CPU acima de 90%",
            "type": "performance",
        }
        plan = planner.create_plan(goal)
        assert isinstance(plan, CognitivePlan)
        assert plan.goal_id == "goal-1"
        assert len(plan.steps) > 0

    def test_plan_steps_are_numbered(self, planner):
        goal = {"id": "g1", "title": "Test", "type": "operational"}
        plan = planner.create_plan(goal)
        for i, step in enumerate(plan.steps):
            assert step.step == i + 1

    def test_performance_plan_has_resource_check(self, planner):
        goal = {
            "id": "g2",
            "title": "Reduzir uso excessivo de RAM",
            "type": "performance",
        }
        plan = planner.create_plan(goal)
        descriptions = [s.description for s in plan.steps]
        assert any("recursos" in d.lower() or "ram" in d.lower() for d in descriptions)

    def test_security_plan_has_suggestion(self, planner):
        goal = {
            "id": "g3",
            "title": "Verificar permissões de arquivo",
            "type": "security",
        }
        plan = planner.create_plan(goal)
        has_suggestion = any(s.action_type == "suggestion" for s in plan.steps)
        assert has_suggestion

    def test_max_risk_property(self, planner):
        plan = CognitivePlan(
            id="p1",
            goal_id="g1",
            steps=[
                PlanStep(step=1, risk="low"),
                PlanStep(step=2, risk="high"),
                PlanStep(step=3, risk="medium"),
            ],
        )
        assert plan.max_risk == "high"

    def test_risk_summary(self, planner):
        goal = {"id": "g4", "title": "Read-only check", "type": "cognitive"}
        plan = planner.create_plan(goal)
        assert plan.risk_summary  # Should have some summary text

    def test_operational_with_create_keyword(self, planner):
        goal = {
            "id": "g5",
            "title": "Criar systemd service",
            "type": "operational",
        }
        plan = planner.create_plan(goal)
        has_write = any(s.action_type == "write" for s in plan.steps)
        assert has_write

    def test_maintenance_with_systemd(self, planner):
        goal = {
            "id": "g6",
            "title": "Verificar systemd service status",
            "type": "maintenance",
        }
        plan = planner.create_plan(goal)
        has_command = any(s.action_type == "command" for s in plan.steps)
        assert has_command

    def test_plan_always_starts_with_diagnostic(self, planner):
        goal = {"id": "g7", "title": "Anything", "type": "operational"}
        plan = planner.create_plan(goal)
        assert plan.steps[0].action_type == "read"
