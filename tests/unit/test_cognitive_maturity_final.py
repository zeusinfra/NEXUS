from zeus_core.cognitive.priority_orchestrator import PriorityOrchestrator
from zeus_core.cognitive.predictive_engine import PredictiveEngine
from zeus_core.security.privacy_guard import PrivacyGuard


class TestCognitiveMaturityFinal:
    def test_priority_orchestrator_deep_focus(self):
        orchestrator = PriorityOrchestrator()
        goals = [
            {"id": "g1", "title": "Cleanup", "priority": 50, "type": "maintenance"},
            {"id": "g2", "title": "Fix Security", "priority": 50, "type": "security"},
        ]
        context = {
            "attention": {"state": "deep_focus", "max_active_goals": 1},
            "perception": {"system": {"cpu_percent": 10}},
        }

        result = orchestrator.orchestrate(goals, context)
        assert len(result.selected_goals) == 1
        # Security should have higher score in deep_focus (multiplier 1.5 vs 0.5)
        assert result.selected_goals[0]["type"] == "security"

    def test_predictive_engine_system_needs(self):
        engine = PredictiveEngine()
        perception = {"system": {"disk_percent": 85}}
        profile = {"temporal": {}, "session": {}}

        proactive = engine.anticipate(profile, perception)
        assert any("Limpeza preventiva" in g["title"] for g in proactive)

    def test_privacy_cognitive_shielding(self):
        guard = PrivacyGuard()
        perception = {
            "files": {
                "config.json": '{"api_key": "sk-123456789012345678901234567890123456789012345678"}'
            },
            "user_input": "Minha senha é sk-123456789012345678901234567890123456789012345678",
        }

        sanitized = guard.sanitize_perception(perception)

        # Verify both file content and user input are masked
        assert "[MASKED_OPENAI_KEY]" in sanitized["files"]["config.json"]
        assert "[MASKED_OPENAI_KEY]" in sanitized["user_input"]
        assert "sk-" not in sanitized["user_input"]
