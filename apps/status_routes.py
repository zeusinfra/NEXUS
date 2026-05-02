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

    return router
