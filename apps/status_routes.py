from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from nexus_core.llm_service import LLMService


@dataclass(frozen=True)
class StatusRouteDeps:
    is_trusted_request: Callable[[Request], bool]
    require_lan_token_for_request: Callable[[Request], None]
    build_api_status: Callable[[], dict]
    build_api_health: Callable[[], dict]
    llm_service: LLMService


def create_status_router(deps: StatusRouteDeps) -> APIRouter:
    router = APIRouter()

    def require_access(request: Request) -> None:
        if not deps.is_trusted_request(request):
            raise HTTPException(
                status_code=403, detail="Only trusted (local/LAN) requests are allowed."
            )
        deps.require_lan_token_for_request(request)

    @router.get("/api/status")
    async def get_api_status(request: Request):
        require_access(request)
        return deps.build_api_status()

    @router.get("/api/llm/status")
    async def get_api_llm_status(request: Request):
        require_access(request)
        return deps.llm_service.get_status()

    @router.post("/api/llm/test")
    async def test_api_llm(request: Request):
        require_access(request)
        return await asyncio.to_thread(deps.llm_service.test_connectivity)

    @router.get("/api/health")
    async def get_api_health(request: Request):
        require_access(request)
        return deps.build_api_health()

    @router.get("/api/applet/status")
    async def get_api_applet_status(request: Request):
        require_access(request)
        from nexus_core.cognitive.cognitive_state import cognitive_state_manager

        # Add cognitive state
        state = cognitive_state_manager.state

        health = deps.build_api_health()
        llm = health.get("llm", {})
        metrics = health.get("metrics", {})
        config = health.get("config", {})

        # Sincronização e Sinapses (Nível 5)
        synapse_count = 0
        try:
            from nexus_core.memory_manager import memory_manager
            import sqlite3
            conn = sqlite3.connect(memory_manager.db_path)
            synapse_count = conn.execute("SELECT COUNT(*) FROM synapses").fetchone()[0]
            conn.close()
        except Exception:
            pass

        from apps.web_gui import sync_engine

        return {
            "ok": True,
            "online": True,
            "api_status": deps.build_api_status(),
            "llm": {
                "provider": llm.get("provider"),
                "model": llm.get("model"),
                "configured": bool(llm.get("configured")),
                "base_url": llm.get("base_url"),
            },
            "cognitive": {
                "attention": state.attention.get("state", "idle"),
                "focus_score": state.attention.get("focus_score", 0.0),
                "active_goals": state.active_goals_list,
                "privacy_shield": state.privacy_status.get("shield"),
                "synapse_count": synapse_count,
            },
            "sync": {
                "is_running": sync_engine.is_running,
                "last_sync": sync_engine.last_sync,
                "relay": sync_engine.relay_url
            },
            "voice": health.get("voice", {}),
            "vision": health.get("vision", {}),
            "second_brain": health.get("second_brain", {}),
            "security": health.get("security", {}),
            "config": {
                "env": config.get("env"),
                "mode": config.get("mode"),
                "auto_evolve": bool(config.get("auto_evolve")),
                "hosted_ollama_api": bool(config.get("hosted_ollama_api")),
                "warnings": config.get("warnings", []),
            },
            "metrics": {
                "http_requests_total": metrics.get("http_requests_total", 0),
            },
        }

    return router
