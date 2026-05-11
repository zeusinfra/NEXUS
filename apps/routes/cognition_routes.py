"""
NEXUS Cognitive Core — FastAPI Routes.

Provides REST endpoints for inspecting and controlling the cognitive system.
Follows the same dependency-injection pattern as ``status_routes.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, HTTPException, Request

from nexus_core.cognitive.cognitive_state import cognitive_state_manager
from nexus_core.cognitive.cognition_service import CognitionService
from nexus_core.cognitive.goal_engine import GoalEngine
from nexus_core.cognitive.reflection_engine import ReflectionEngine
from nexus_core.cognitive.execution_engine import CognitiveExecutionEngine


@dataclass(frozen=True)
class CognitionRouteDeps:
    """Dependencies injected from the host application."""

    is_trusted_request: Callable[[Request], bool]
    require_lan_token_for_request: Callable[[Request], None]
    cognition_service: CognitionService


def create_cognition_router(deps: CognitionRouteDeps) -> APIRouter:
    """Create the /api/cognition router."""
    router = APIRouter(prefix="/api/cognition", tags=["cognition"])

    db_path = deps.cognition_service.db_path
    goal_engine = GoalEngine(db_path=db_path)
    reflection_engine = ReflectionEngine(db_path=db_path)
    execution_engine = CognitiveExecutionEngine(db_path=db_path)

    def require_access(request: Request) -> None:
        if not deps.is_trusted_request(request):
            raise HTTPException(
                status_code=403, detail="Only trusted (local/LAN) requests are allowed."
            )
        deps.require_lan_token_for_request(request)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @router.get("/status")
    async def get_cognition_status(request: Request):
        """Return the current cognitive state."""
        require_access(request)
        return cognitive_state_manager.get_snapshot()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @router.post("/start")
    async def start_cognition(request: Request):
        """Start the cognitive loop."""
        require_access(request)
        started = await deps.cognition_service.start()
        if not started:
            return {"status": "already_running"}
        return {"status": "started"}

    @router.post("/stop")
    async def stop_cognition(request: Request):
        """Stop the cognitive loop."""
        require_access(request)
        stopped = await deps.cognition_service.stop()
        if not stopped:
            return {"status": "not_running"}
        return {"status": "stopped"}

    # ------------------------------------------------------------------
    # Goals
    # ------------------------------------------------------------------

    @router.get("/goals")
    async def list_goals(request: Request, status: str | None = None, limit: int = 50):
        """List cognitive goals, optionally filtered by status."""
        require_access(request)
        goals = goal_engine.list_goals(status=status, limit=limit)
        return {"goals": [g.to_dict() for g in goals], "count": len(goals)}

    # ------------------------------------------------------------------
    # Reflections
    # ------------------------------------------------------------------

    @router.get("/reflections")
    async def list_reflections(
        request: Request,
        type: str | None = None,
        limit: int = 20,
    ):
        """List cognitive reflections."""
        require_access(request)
        refs = reflection_engine.list_reflections(reflection_type=type, limit=limit)
        return {"reflections": [r.to_dict() for r in refs], "count": len(refs)}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @router.get("/actions")
    async def list_actions(
        request: Request, status: str | None = None, limit: int = 50
    ):
        """List cognitive actions."""
        require_access(request)
        actions = execution_engine.list_actions(status=status, limit=limit)
        return {"actions": [a.to_dict() for a in actions], "count": len(actions)}

    @router.post("/actions/{action_id}/approve")
    async def approve_action(request: Request, action_id: str):
        """Approve and execute a pending action."""
        require_access(request)
        result = execution_engine.approve_action(action_id)
        if not result:
            raise HTTPException(
                status_code=404, detail="Action not found or not pending confirmation."
            )
        return result.to_dict()

    # ------------------------------------------------------------------
    # User Profile
    # ------------------------------------------------------------------

    @router.get("/profile")
    async def get_user_profile(request: Request):
        """Return the current user profile summary."""
        require_access(request)
        # We reuse the user_profile instance from the service if available
        # But for the router, we can create a temporary one or access it via service
        # Let's assume the service exposes it
        if hasattr(deps.cognition_service.loop, "user_profile"):
            return deps.cognition_service.loop.user_profile.get_profile_summary()
        return {"error": "User Profile Engine not active"}

    @router.get("/habits")
    async def list_habits(request: Request, limit: int = 20):
        """List detected user habits."""
        require_access(request)
        if hasattr(deps.cognition_service.loop, "user_profile"):
            habits = deps.cognition_service.loop.user_profile.list_habits(limit=limit)
            return {"habits": [h.to_dict() for h in habits], "count": len(habits)}
        return {"habits": [], "count": 0}

    @router.get("/workflows")
    async def list_workflows(request: Request, limit: int = 20):
        """List detected user workflows."""
        require_access(request)
        if hasattr(deps.cognition_service.loop, "user_profile"):
            wfs = deps.cognition_service.loop.user_profile.list_workflows(limit=limit)
            return {"workflows": [w.to_dict() for w in wfs], "count": len(wfs)}
        return {"workflows": [], "count": 0}

    return router
