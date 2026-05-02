from __future__ import annotations

import importlib.util
import shutil
import time
from typing import Any

import requests


def check_memory_service(url: str = "http://127.0.0.1:8082/health", timeout: float = 0.35) -> dict[str, Any]:
    try:
        resp = requests.get(url, timeout=timeout)
        return {"status": "online" if resp.status_code == 200 else "offline"}
    except Exception:
        return {"status": "offline"}


def build_watcher_status(process: Any, started_at: float | None, last_event_at: float | None) -> dict[str, Any]:
    running = bool(process and process.returncode is None)
    return {
        "status": "online" if running else "offline",
        "pid": process.pid if process else None,
        "uptime_s": round(time.time() - started_at) if started_at else None,
        "last_event_age_s": round(time.time() - last_event_at) if last_event_at else None,
    }


def build_runtime_health(
    *,
    llm: dict[str, Any],
    watcher: dict[str, Any],
    enable_voice: bool,
    enable_voice_sensing: bool,
    allow_lan: bool,
    lan_auth_enabled: bool,
    remote_auth_required: bool,
    bind_host: str,
    ocr_available: bool,
) -> dict[str, Any]:
    ffmpeg_available = bool(shutil.which("ffmpeg"))
    return {
        "llm": llm,
        "memory": check_memory_service(),
        "watcher": watcher,
        "voice": {
            "enabled": bool(enable_voice),
            "sensing_enabled": bool(enable_voice_sensing),
        },
        "asr": {
            "backend_available": ffmpeg_available and (importlib.util.find_spec("faster_whisper") is not None),
            "ffmpeg_available": ffmpeg_available,
        },
        "vision": {
            "ocr_available": bool(ocr_available),
            "screen_capture_available": True,
        },
        "security": {
            "allow_lan": bool(allow_lan),
            "lan_auth_enabled": bool(lan_auth_enabled),
            "remote_auth_required": bool(remote_auth_required),
            "bind_host": bind_host,
        },
    }
