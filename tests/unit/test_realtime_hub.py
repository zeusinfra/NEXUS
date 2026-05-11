import unittest

from apps.realtime_hub import RealtimeHub


class FakeSio:
    def __init__(self):
        self.emitted = []
        self.handlers = {}

    async def emit(self, event, msg, to=None):
        self.emitted.append((event, msg, to))

    def on(self, event):
        def decorator(fn):
            self.handlers[event] = fn
            return fn

        return decorator


class FakeWebSocket:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.sent = []

    async def send_text(self, payload):
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append(payload)


class RealtimeHubTests(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_emits_to_socketio_and_native_websocket(self):
        sio = FakeSio()
        hub = RealtimeHub(sio)
        ws = FakeWebSocket()
        hub.ws_clients.add(ws)

        await hub.broadcast_message({"type": "status", "ok": True})

        self.assertEqual(sio.emitted[0][0], "message")
        self.assertIn('"type": "status"', ws.sent[0])

    async def test_broadcast_removes_dead_websocket(self):
        hub = RealtimeHub(FakeSio())
        ws = FakeWebSocket(fail=True)
        hub.ws_clients.add(ws)

        await hub.broadcast_message({"type": "status"})

        self.assertNotIn(ws, hub.ws_clients)

    async def test_drain_inbox_returns_and_clears_pending_messages(self):
        hub = RealtimeHub(FakeSio())

        await hub.broadcast_message({"type": "chat", "client_id": "client-1"})

        self.assertEqual(len(hub.drain_inbox("client-1")), 1)
        self.assertEqual(hub.drain_inbox("client-1"), [])


if __name__ == "__main__":
    unittest.main()
