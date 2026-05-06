"""
ZEUS Cognitive Core — Predictive Engine.

Anticipates user needs and system events based on habits,
workflows, and historical patterns.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, List

from zeus_core.observability import get_logger, log_event

logger = get_logger("zeus.cognitive.predictive")

class PredictiveEngine:
    """Anticipation and proactivity engine."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    def anticipate(self, profile: dict, perception: dict) -> List[dict]:
        """
        Generate proactive goal suggestions based on the current state.
        Returns a list of goal-like dictionaries to be reviewed by the Orchestrator.
        """
        proactive_goals = []

        # 1. Workflow Foresight
        workflow_goals = self._anticipate_workflows(profile)
        proactive_goals.extend(workflow_goals)

        # 2. Habit Anomaly Detection
        habit_goals = self._detect_missing_habits(profile)
        proactive_goals.extend(habit_goals)

        # 3. System Foresight (Anticipatory Maintenance)
        system_goals = self._anticipate_system_needs(perception)
        proactive_goals.extend(system_goals)

        if proactive_goals:
            log_event(logger, 20, "proactive_goals_generated", count=len(proactive_goals))

        return proactive_goals

    def _anticipate_workflows(self, profile: dict) -> List[dict]:
        """If a workflow is active, suggest the next step."""
        goals = []
        active_wf_name = profile.get("temporal", {}).get("active_workflow")
        if not active_wf_name:
            return []

        # Find the workflow details in habits/workflows
        workflows = profile.get("workflows", [])
        wf = next((w for w in workflows if w["name"] == active_wf_name), None)
        if not wf:
            return []

        # Logic: find where the user is and suggest next
        # In this implementation, we simply suggest preparing for the next phase
        goals.append({
            "title": f"Antecipar próximo passo do workflow: {active_wf_name}",
            "description": f"Workflow detectado com {wf.get('confidence', 0):.0%} de confiança. Preparando contexto.",
            "type": "proactive",
            "priority": 40,
            "risk": "low"
        })
        return goals

    def _detect_missing_habits(self, profile: dict) -> List[dict]:
        """Check if an expected habit is not occurring."""
        goals = []
        temporal = profile.get("temporal", {})
        expected = temporal.get("expected_habits", [])
        
        # This requires session awareness. If a habit is expected but session is idle:
        if expected and not profile.get("session", {}).get("active"):
             for habit in expected:
                 goals.append({
                     "title": f"Propor início de hábito: {habit}",
                     "description": "Este comportamento é comum neste horário. Deseja assistência?",
                     "type": "proactive",
                     "priority": 30,
                     "risk": "low"
                 })
        return goals

    def _anticipate_system_needs(self, perception: dict) -> List[dict]:
        """Predict issues based on trends."""
        goals = []
        sys = perception.get("system", {})
        disk = sys.get("disk_percent", 0)
        
        # If disk is > 70% and increasing, suggest proactive cleanup before it hits 90%
        if disk > 70:
            goals.append({
                "title": "Limpeza preventiva de disco",
                "description": f"O disco está em {disk}%. Antecipando necessidade de manutenção.",
                "type": "maintenance",
                "priority": 45,
                "risk": "low"
            })
            
        return goals
