"""
ZEUS Cognitive Core — Package Init.

Public API for the cognitive subsystem.
"""

from nexus_core.cognitive.cognitive_state import cognitive_state_manager
from nexus_core.cognitive.cognition_service import CognitionService

__all__ = [
    "cognitive_state_manager",
    "CognitionService",
]
