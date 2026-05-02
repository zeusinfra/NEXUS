from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from zeus_core.llm_service import LLMService


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
            raise HTTPException(status_code=403, detail="Only trusted (local/LAN) requests are allowed.")
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
        health = deps.build_api_health()
        llm = health.get("llm", {})
        metrics = health.get("metrics", {})
        config = health.get("config", {})
        return {
            "ok": True,
            "online": True,
            "llm": {
                "provider": llm.get("provider"),
                "model": llm.get("model"),
                "configured": bool(llm.get("configured")),
                "base_url": llm.get("base_url"),
            },
            "voice": health.get("voice", {}),
            "vision": health.get("vision", {}),
            "security": health.get("security", {}),
            "config": {
                "env": config.get("env"),
                "hosted_ollama_api": bool(config.get("hosted_ollama_api")),
                "warnings": config.get("warnings", []),
            },
            "metrics": {
                "http_requests_total": metrics.get("http_requests_total", 0),
            },
        }

    return router
