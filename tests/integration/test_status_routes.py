import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from apps.status_routes import StatusRouteDeps, create_status_router
from nexus_core.llm_service import LLMService


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(
            route, "methods", set()
        ):
            return route.endpoint
    raise AssertionError(f"endpoint not found: {method} {path}")


class StatusRoutesTests(unittest.IsolatedAsyncioTestCase):
    def _router(self, *, trusted=True, token_error=None):
        calls = {"token": 0}

        def require_token(request):
            calls["token"] += 1
            if token_error:
                raise token_error

        router = create_status_router(
            StatusRouteDeps(
                is_trusted_request=lambda request: trusted,
                require_lan_token_for_request=require_token,
                build_api_status=lambda: {"cpu": 1.0, "mood": "CALM"},
                build_api_health=lambda: {
                    "llm": {"provider": "test"},
                    "config": {"warnings": []},
                    "second_brain": {"enabled": True, "sync_engine_enabled": False},
                },
                llm_service=LLMService(
                    get_status=lambda: {"provider": "test", "configured": True},
                    call_llm=lambda messages: "NEXUS LLM OK",
                ),
            )
        )
        return router, calls

    async def test_health_route_requires_access_and_returns_payload(self):
        router, calls = self._router()
        endpoint = _endpoint(router, "/api/health", "GET")

        result = await endpoint(SimpleNamespace())

        self.assertEqual(result["llm"]["provider"], "test")
        self.assertEqual(calls["token"], 1)

    async def test_applet_status_returns_compact_payload(self):
        router, calls = self._router()
        endpoint = _endpoint(router, "/api/applet/status", "GET")

        result = await endpoint(SimpleNamespace())

        self.assertTrue(result["ok"])
        self.assertTrue(result["online"])
        self.assertEqual(result["llm"]["provider"], "test")
        self.assertEqual(result["config"]["warnings"], [])
        self.assertTrue(result["second_brain"]["enabled"])
        self.assertFalse(result["second_brain"]["sync_engine_enabled"])
        self.assertEqual(calls["token"], 1)

    async def test_llm_status_route_returns_sanitized_status(self):
        router, _ = self._router()
        endpoint = _endpoint(router, "/api/llm/status", "GET")

        result = await endpoint(SimpleNamespace())

        self.assertEqual(result["provider"], "test")
        self.assertNotIn("api_key", result)

    async def test_llm_test_route_runs_connectivity(self):
        router, _ = self._router()
        endpoint = _endpoint(router, "/api/llm/test", "POST")

        async def immediate_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("apps.status_routes.asyncio.to_thread", immediate_to_thread):
            result = await endpoint(SimpleNamespace())

        self.assertTrue(result["ok"])
        self.assertEqual(result["reply"], "NEXUS LLM OK")

    async def test_untrusted_request_is_rejected(self):
        router, _ = self._router(trusted=False)
        endpoint = _endpoint(router, "/api/status", "GET")

        with self.assertRaises(HTTPException) as ctx:
            await endpoint(SimpleNamespace())
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_lan_token_error_is_propagated(self):
        router, _ = self._router(
            token_error=HTTPException(status_code=401, detail="bad token")
        )
        endpoint = _endpoint(router, "/api/status", "GET")

        with self.assertRaises(HTTPException) as ctx:
            await endpoint(SimpleNamespace())
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
