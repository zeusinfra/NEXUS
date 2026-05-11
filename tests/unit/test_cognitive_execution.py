"""Tests for the cognitive execution engine."""

import pytest

from nexus_core.cognitive.cognitive_db import init_cognitive_tables
from nexus_core.cognitive.execution_engine import CognitiveExecutionEngine, ActionResult


@pytest.fixture
def engine(tmp_path):
    db = str(tmp_path / "test_execution.db")
    init_cognitive_tables(db)
    return CognitiveExecutionEngine(db_path=db)


class TestCognitiveExecutionEngine:
    def test_execute_read_step(self, engine):
        step = {"action_type": "read", "description": "Check system", "risk": "low"}
        result = engine.execute_step("plan-1", 0, step)
        assert result.status == "success"
        assert "[READ]" in result.output

    def test_execute_memory_step(self, engine):
        step = {"action_type": "memory", "description": "Query memory", "risk": "low"}
        result = engine.execute_step("plan-1", 0, step)
        assert result.status == "success"

    def test_execute_suggestion_step(self, engine):
        step = {
            "action_type": "suggestion",
            "description": "Suggest action",
            "risk": "low",
        }
        result = engine.execute_step("plan-1", 0, step)
        assert result.status == "success"

    def test_execute_safe_command(self, engine):
        step = {"action_type": "command", "command": "echo hello", "risk": "low"}
        result = engine.execute_step("plan-1", 0, step)
        assert result.status == "success"
        assert "hello" in result.output

    def test_execute_blocked_command(self, engine):
        step = {"action_type": "command", "command": "rm -rf /", "risk": "critical"}
        result = engine.execute_step("plan-1", 0, step)
        assert result.status == "blocked"
        assert result.error  # Should have an error message

    def test_write_step_requires_confirmation(self, engine):
        step = {"action_type": "write", "description": "Write file", "risk": "medium"}
        result = engine.execute_step("plan-1", 0, step)
        assert result.status == "requires_confirmation"

    def test_propose_action(self, engine):
        step = {
            "action_type": "command",
            "description": "Install package",
            "risk": "high",
        }
        result = engine.propose_action("plan-1", 0, step)
        assert result.status == "requires_confirmation"
        assert result.risk == "high"

    def test_audit_action_persists(self, engine):
        result = ActionResult(
            id="test-action-1",
            plan_id="plan-1",
            step_index=0,
            action_type="read",
            status="success",
            output="test output",
            created_at="2026-01-01T00:00:00Z",
        )
        engine.audit_action(result)

        actions = engine.list_actions()
        assert len(actions) >= 1
        assert actions[0].id == "test-action-1"

    def test_list_actions_filter_by_status(self, engine):
        r1 = ActionResult(
            id="a1",
            plan_id="p1",
            step_index=0,
            status="success",
            created_at="2026-01-01T00:00:00Z",
        )
        r2 = ActionResult(
            id="a2",
            plan_id="p1",
            step_index=1,
            status="requires_confirmation",
            created_at="2026-01-01T00:00:01Z",
        )
        engine.audit_action(r1)
        engine.audit_action(r2)

        pending = engine.list_actions(status="requires_confirmation")
        assert len(pending) == 1
        assert pending[0].id == "a2"

    def test_get_pending_confirmations(self, engine):
        r1 = ActionResult(
            id="p1",
            plan_id="p1",
            step_index=0,
            status="requires_confirmation",
            created_at="2026-01-01T00:00:00Z",
        )
        engine.audit_action(r1)
        pending = engine.get_pending_confirmations()
        assert len(pending) >= 1

    def test_execute_plan_with_simulation(self, engine):
        plan = {
            "id": "plan-safe",
            "steps": [
                {
                    "step": 1,
                    "action_type": "read",
                    "description": "Check",
                    "risk": "low",
                },
                {
                    "step": 2,
                    "action_type": "suggestion",
                    "description": "Suggest",
                    "risk": "low",
                },
            ],
        }
        simulation = {
            "approved_for_auto_execution": True,
            "step_results": [
                {
                    "step": 1,
                    "risk": "low",
                    "blocked": False,
                    "requires_confirmation": False,
                },
                {
                    "step": 2,
                    "risk": "low",
                    "blocked": False,
                    "requires_confirmation": False,
                },
            ],
        }
        results = engine.execute_plan(plan, simulation)
        assert len(results) == 2
        assert all(r.status == "success" for r in results)
