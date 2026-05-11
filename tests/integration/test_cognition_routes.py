"""Tests for the cognition API routes."""

import pytest
from types import SimpleNamespace

from fastapi import HTTPException

from zeus_core.cognitive.cognitive_db import init_cognitive_tables
from zeus_core.cognitive.cognition_service import CognitionService
from apps.routes.cognition_routes import CognitionRouteDeps, create_cognition_router


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(
            route, "methods", set()
        ):
            return route.endpoint
    raise AssertionError(f"endpoint not found: {method} {path}")


@pytest.fixture
def router(tmp_path):
    db = str(tmp_path / "test_routes.db")
    init_cognitive_tables(db)

    service = CognitionService(db_path=db)

    deps = CognitionRouteDeps(
        is_trusted_request=lambda r: True,
        require_lan_token_for_request=lambda r: None,
        cognition_service=service,
    )

    return create_cognition_router(deps)


class TestCognitionRoutes:
    @pytest.mark.asyncio
    async def test_get_status(self, router):
        endpoint = _endpoint(router, "/api/cognition/status", "GET")
        data = await endpoint(SimpleNamespace())
        assert "mode" in data
        assert "loop_running" in data
        assert "health_score" in data

    @pytest.mark.asyncio
    async def test_get_goals_empty(self, router):
        endpoint = _endpoint(router, "/api/cognition/goals", "GET")
        data = await endpoint(SimpleNamespace())
        assert "goals" in data
        assert isinstance(data["goals"], list)

    @pytest.mark.asyncio
    async def test_get_reflections_empty(self, router):
        endpoint = _endpoint(router, "/api/cognition/reflections", "GET")
        data = await endpoint(SimpleNamespace())
        assert "reflections" in data

    @pytest.mark.asyncio
    async def test_get_actions_empty(self, router):
        endpoint = _endpoint(router, "/api/cognition/actions", "GET")
        data = await endpoint(SimpleNamespace())
        assert "actions" in data

    @pytest.mark.asyncio
    async def test_approve_nonexistent_action(self, router):
        endpoint = _endpoint(
            router, "/api/cognition/actions/{action_id}/approve", "POST"
        )
        with pytest.raises(HTTPException) as exc:
            await endpoint(SimpleNamespace(), "nonexistent")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, router):
        endpoint = _endpoint(router, "/api/cognition/stop", "POST")
        data = await endpoint(SimpleNamespace())
        assert data["status"] == "not_running"
