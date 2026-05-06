"""Tests for the cognition API routes."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from zeus_core.cognitive.cognitive_db import init_cognitive_tables
from zeus_core.cognitive.cognition_service import CognitionService
from apps.routes.cognition_routes import CognitionRouteDeps, create_cognition_router


@pytest.fixture
def test_app(tmp_path):
    db = str(tmp_path / "test_routes.db")
    init_cognitive_tables(db)

    service = CognitionService(db_path=db)

    deps = CognitionRouteDeps(
        is_trusted_request=lambda r: True,
        require_lan_token_for_request=lambda r: None,
        cognition_service=service,
    )

    app = FastAPI()
    app.include_router(create_cognition_router(deps))
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


class TestCognitionRoutes:
    def test_get_status(self, client):
        resp = client.get("/api/cognition/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert "loop_running" in data
        assert "health_score" in data

    def test_get_goals_empty(self, client):
        resp = client.get("/api/cognition/goals")
        assert resp.status_code == 200
        data = resp.json()
        assert "goals" in data
        assert isinstance(data["goals"], list)

    def test_get_reflections_empty(self, client):
        resp = client.get("/api/cognition/reflections")
        assert resp.status_code == 200
        data = resp.json()
        assert "reflections" in data

    def test_get_actions_empty(self, client):
        resp = client.get("/api/cognition/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data

    def test_approve_nonexistent_action(self, client):
        resp = client.post("/api/cognition/actions/nonexistent/approve")
        assert resp.status_code == 404

    def test_stop_when_not_running(self, client):
        resp = client.post("/api/cognition/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_running"
