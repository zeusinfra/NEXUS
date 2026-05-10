from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import WebSocket, WebSocketDisconnect


@dataclass(frozen=True)
class RealtimeDeps:
    is_trusted_host: Callable[[str | None], bool]
    require_lan_token_for_socketio: Callable[[dict, dict | None], bool]
    build_init_payload: Callable[[], dict]
    remote_auth_required: Callable[[], bool]
    lan_auth_enabled: bool
    lan_token: str
    is_local_host: Callable[[str | None], bool]
    extract_bearer_token: Callable[[str | None], str | None]
    handle_client_text: Callable[[str], Awaitable[None]]
    handle_client_voice_start: Callable[[], Awaitable[None]]
    handle_client_vision: Callable[[], Awaitable[None]]
    handle_arm_voice: Callable[[int], Awaitable[None]]


class RealtimeHub:
    def __init__(self, sio):
        self.sio = sio
        self.socketio_clients: set[str] = set()
        self.ws_clients: set[WebSocket] = set()
        self.client_inboxes: dict[str, list[dict]] = {}

    def register_socketio_handlers(self, deps: RealtimeDeps) -> None:
        @self.sio.on("connect")
        async def handle_connect(sid, environ, auth_payload=None):
            host = self._host_from_environ(environ)
            if not deps.is_trusted_host(host):
                print(f"[Socket.io] REJECTED connect from untrusted host: {host}")
                return False
            if not deps.require_lan_token_for_socketio(environ, auth_payload):
                print(f"[Socket.io] REJECTED connect (invalid/missing token) host={host}")
                return False
            self.socketio_clients.add(sid)
            print(f"[Socket.io] Client connected: {sid}")
            try:
                await self.sio.emit("message", deps.build_init_payload(), to=sid)
            except Exception as e:
                print(f"[Socket.io] Failed to send init payload to {sid}: {e}")

        @self.sio.on("disconnect")
        async def handle_disconnect(sid):
            self.socketio_clients.discard(sid)
            print(f"[Socket.io] Client disconnected: {sid}")

        @self.sio.on("audio_stream")
        async def handle_audio_stream(sid, data):
            try:
                if isinstance(data, dict) and "audio" in data:
                    chunk = data["audio"]
                    print(f"[Socket.io] Received audio chunk from {sid} (size: {len(chunk)} bytes)")
                else:
                    print(f"[Socket.io] Invalid audio stream payload from {sid}")
            except Exception as e:
                print(f"[Socket.io] Error processing audio stream: {e}")

        @self.sio.on("arm_voice")
        async def handle_arm_voice(sid, data):
            duration = data.get("duration", 10) if isinstance(data, dict) else 10
            await deps.handle_arm_voice(duration)

    async def broadcast_message(self, msg: dict) -> None:
        try:
            await self.sio.emit("message", msg)
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f" [BROADCAST ERROR] {e} | MSG: {str(msg)[:200]}")

        if self.ws_clients:
            dead = set()
            payload = json.dumps(msg, ensure_ascii=False)
            for ws in self.ws_clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                self.ws_clients.discard(ws)

        cid = msg.get("client_id")
        if cid:
            self.client_inboxes.setdefault(cid, []).append(msg)
            if len(self.client_inboxes[cid]) > 20:
                self.client_inboxes[cid].pop(0)

    def drain_inbox(self, client_id: str | None) -> list[dict]:
        if not client_id or client_id not in self.client_inboxes:
            return []
        pending = self.client_inboxes[client_id][:]
        self.client_inboxes[client_id] = []
        return pending

    async def websocket_client(self, websocket: WebSocket, deps: RealtimeDeps) -> None:
        host = getattr(websocket.client, "host", None)
        if not deps.is_trusted_host(host):
            await websocket.close(code=1008)
            return
        if deps.remote_auth_required() and deps.lan_auth_enabled and not deps.is_local_host(host):
            provided = deps.extract_bearer_token(websocket.query_params.get("token"))
            provided = provided or deps.extract_bearer_token(websocket.query_params.get("lan"))
            provided = provided or deps.extract_bearer_token(websocket.query_params.get("lan_token"))
            if not deps.lan_token or provided != deps.lan_token:
                await websocket.close(code=1008)
                return

        await websocket.accept()
        self.ws_clients.add(websocket)
        print(f"[WS] Client connected: {websocket.client}")

        try:
            await websocket.send_text(json.dumps(deps.build_init_payload(), ensure_ascii=False))
        except Exception as e:
            print(f"[WS] Failed to send init payload: {e}")

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                event_id = data.get("event_id")
                if event_id:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "ack",
                                "event_id": event_id,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "payload": {},
                            }
                        )
                    )

                if msg_type == "user_input":
                    text = (data.get("payload") or {}).get("text", "").strip()
                    if text and text not in ("__voice_start__", "__vision_analyze__"):
                        await deps.handle_client_text(text)
                    elif text == "__voice_start__":
                        await deps.handle_client_voice_start()
                    elif text == "__vision_analyze__":
                        await deps.handle_client_vision()

                elif msg_type == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong", "payload": {"ts": int(time.time() * 1000)}})
                    )

                elif msg_type == "arm_voice":
                    duration = (data.get("payload") or {}).get("duration", 10)
                    await deps.handle_arm_voice(duration)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[WS] Client error: {e}")
        finally:
            self.ws_clients.discard(websocket)
            print(f"[WS] Client disconnected: {websocket.client}")

    @staticmethod
    def _host_from_environ(environ: dict) -> str | None:
        try:
            host = environ.get("REMOTE_ADDR")
        except Exception:
            host = None
        if host:
            return host
        try:
            scope = environ.get("asgi.scope") or {}
            client = scope.get("client")
            return client[0] if isinstance(client, (list, tuple)) and client else None
        except Exception:
            return None
