from __future__ import annotations

import importlib.util
import socket
import shutil
import time
from pathlib import Path
from typing import Any

import psutil
import requests


def check_memory_service(
    url: str = "http://127.0.0.1:8082/health", timeout: float = 0.35
) -> dict[str, Any]:
    try:
        resp = requests.get(url, timeout=timeout)
        return {"status": "online" if resp.status_code == 200 else "offline"}
    except Exception:
        return {"status": "offline"}


def build_watcher_status(
    process: Any, started_at: float | None, last_event_at: float | None
) -> dict[str, Any]:
    running = bool(process and process.returncode is None)
    return {
        "status": "online" if running else "offline",
        "pid": process.pid if process else None,
        "uptime_s": round(time.time() - started_at) if started_at else None,
        "last_event_age_s": round(time.time() - last_event_at)
        if last_event_at
        else None,
    }


def _watcher_command_matches(
    cmdline: list[str], project_root: str | Path | None = None
) -> bool:
    command = " ".join(str(part) for part in cmdline)
    if "watcher_rs" not in command:
        return False
    if project_root is None:
        return True
    try:
        root = str(Path(project_root).resolve())
    except Exception:
        root = str(project_root)
    return (
        root in command
        or "target/release/watcher_rs" in command
        or "cargo run --release" in command
    )


def _watcher_port_open(
    host: str = "127.0.0.1", port: int = 8081, timeout: float = 0.2
) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_external_watcher_status(
    project_root: str | Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8081,
) -> dict[str, Any]:
    process_info: dict[str, Any] | None = None
    for proc in psutil.process_iter(["pid", "cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if _watcher_command_matches(cmdline, project_root):
                process_info = proc.info
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    port_open = _watcher_port_open(host=host, port=port)
    running = bool(process_info or port_open)
    started_at = process_info.get("create_time") if process_info else None
    return {
        "status": "online" if running else "offline",
        "pid": process_info.get("pid") if process_info else None,
        "uptime_s": round(time.time() - started_at) if started_at else None,
        "last_event_age_s": None,
        "mode": "external",
        "port": port,
        "port_open": port_open,
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
            "backend_available": ffmpeg_available
            and (importlib.util.find_spec("faster_whisper") is not None),
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
