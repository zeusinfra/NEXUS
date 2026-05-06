"""
ZEUS Privacy Guard — FastAPI Routes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from zeus_core.security.privacy_guard import PrivacyGuard


class ConsentRequest(BaseModel):
    resource: str
    scope: str = "session"
    duration_min: int = 30

@dataclass(frozen=True)
class PrivacyRouteDeps:
    is_trusted_request: Callable[[Request], bool]
    require_lan_token_for_request: Callable[[Request], None]
    privacy_guard: PrivacyGuard

def create_privacy_router(deps: PrivacyRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/privacy", tags=["privacy"])

    def require_access(request: Request) -> None:
        if not deps.is_trusted_request(request):
            raise HTTPException(status_code=403, detail="Only trusted (local/LAN) requests are allowed.")
        deps.require_lan_token_for_request(request)

    @router.get("/status")
    async def get_privacy_status(request: Request):
        require_access(request)
        return {
            "mode": deps.privacy_guard.mode,
            "audit_enabled": True,
            "active_consents_count": 0, # Could be expanded
        }

    @router.get("/audit")
    async def get_audit_logs(request: Request, limit: int = 50):
        require_access(request)
        logs = deps.privacy_guard.get_audit_logs(limit=limit)
        return {"logs": logs, "count": len(logs)}

    @router.post("/consent")
    async def grant_consent(request: Request, body: ConsentRequest):
        require_access(request)
        cid = deps.privacy_guard.grant_consent(
            body.resource, scope=body.scope, duration_min=body.duration_min
        )
        return {"status": "granted", "id": cid}

    @router.delete("/consent/{resource}")
    async def revoke_consent(request: Request, resource: str):
        require_access(request)
        deps.privacy_guard.revoke_consent(resource)
        return {"status": "revoked"}

    return router
