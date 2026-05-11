import json
import logging
import unittest
from types import SimpleNamespace

from zeus_core.observability import JsonFormatter, correlation_id_middleware, get_metrics_snapshot, metrics_counter


class FakeResponse:
    def __init__(self):
        self.headers = {}
        self.status_code = 200


class ObservabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_correlation_id_middleware_preserves_incoming_header(self):
        metrics_counter.clear()
        request = SimpleNamespace(
            headers={"x-correlation-id": "trace-123"},
            method="GET",
            url=SimpleNamespace(path="/api/health"),
        )

        async def call_next(req):
            return FakeResponse()

        response = await correlation_id_middleware(request, call_next)

        self.assertEqual(response.headers["x-correlation-id"], "trace-123")
        self.assertEqual(get_metrics_snapshot()["http_requests_total"], 1)

    async def test_correlation_id_middleware_generates_missing_header(self):
        request = SimpleNamespace(
            headers={},
            method="GET",
            url=SimpleNamespace(path="/api/health"),
        )

        async def call_next(req):
            return FakeResponse()

        response = await correlation_id_middleware(request, call_next)

        self.assertTrue(response.headers["x-correlation-id"])

    def test_json_formatter_outputs_structured_record(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="zeus.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"component": "test"}

        payload = json.loads(formatter.format(record))

        self.assertEqual(payload["level"], "info")
        self.assertEqual(payload["logger"], "zeus.test")
        self.assertEqual(payload["message"], "hello")
        self.assertEqual(payload["component"], "test")


if __name__ == "__main__":
    unittest.main()
