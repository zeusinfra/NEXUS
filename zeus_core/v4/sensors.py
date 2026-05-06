from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from zeus_core.v4.types import Event


def _now() -> float:
    return time.time()


try:
    from zeus_sensors import SensorEngineRust
    RUST_SENSORS_AVAILABLE = True
except ImportError:
    RUST_SENSORS_AVAILABLE = False

@dataclass(slots=True)
class OsMetricsSensor:
    def __init__(self):
        if RUST_SENSORS_AVAILABLE:
            self.rust_engine = SensorEngineRust()
        else:
            self.rust_engine = None

    def poll(self) -> list[Event]:
        if self.rust_engine:
            metrics = self.rust_engine.poll_os_metrics()
            cpu = metrics.get("cpu", 0.0)
            mem = metrics.get("mem", 0.0)
            # Disk via psutil por enquanto
            disk = psutil.disk_usage("/").percent
        else:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
        pressure = "CALM"
        if cpu > 80 or mem > 85 or disk > 90:
            pressure = "CRITICAL"
        elif cpu > 55 or mem > 70:
            pressure = "ACTIVE"
        return [
            Event(
                kind="os",
                ts=_now(),
                summary=f"OS pressure={pressure} cpu={cpu}% mem={mem}% disk={disk}%",
                data={"cpu": cpu, "mem": mem, "disk": disk, "pressure": pressure},
                relevance=0.35 if pressure != "CALM" else 0.12,
            )
        ]


class FilePollSensor:
    def __init__(self, roots: list[str], *, max_events: int = 30):
        self.roots = [Path(r).resolve() for r in roots]
        self.max_events = max_events
        self._mtimes: dict[str, float] = {}
        self.max_checked = int(os.getenv("ZEUS_V4_FS_MAX_CHECKED", "1200"))
        self.max_seconds = float(os.getenv("ZEUS_V4_FS_MAX_SECONDS", "0.35"))
        
        if RUST_SENSORS_AVAILABLE:
            self.rust_engine = SensorEngineRust()
        else:
            self.rust_engine = None

    def poll(self) -> list[Event]:
        evs: list[Event] = []
        
        if self.rust_engine:
            for root in self.roots:
                if not root.exists():
                    continue
                raw_results = self.rust_engine.fast_walk(str(root), self.max_checked)
                for path, mtime in raw_results:
                    prev = self._mtimes.get(path)
                    self._mtimes[path] = mtime
                    if prev is not None and mtime > prev:
                        evs.append(
                            Event(
                                kind="fs",
                                ts=_now(),
                                summary=f"File changed (Rust): {os.path.basename(path)}",
                                data={"path": path},
                                relevance=0.25,
                            )
                        )
                        if len(evs) >= self.max_events:
                            return evs
            return evs

        t0 = _now()
        checked = 0
        for root in self.roots:
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                # prune heavy dirs
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d not in {".git", ".venv", "__pycache__", "node_modules", "target", "dist", "build"}
                ]
                for fn in filenames:
                    checked += 1
                    if checked >= self.max_checked or (_now() - t0) >= self.max_seconds:
                        return evs
                    p = Path(dirpath) / fn
                    try:
                        mtime = p.stat().st_mtime
                    except Exception:
                        continue
                    key = str(p)
                    prev = self._mtimes.get(key)
                    self._mtimes[key] = mtime
                    if prev is None:
                        continue
                    if mtime > prev:
                        evs.append(
                            Event(
                                kind="fs",
                                ts=_now(),
                                summary=f"File changed: {p.name}",
                                data={"path": key},
                                relevance=0.25,
                            )
                        )
                        if len(evs) >= self.max_events:
                            return evs
        return evs


class UserInboxSensor:
    def __init__(self, inbox_path: str):
        self.path = Path(inbox_path)
        self._pos = 0

    def poll(self) -> list[Event]:
        if not self.path.exists():
            return []
        try:
            data = self.path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        if self._pos >= len(data):
            return []
        new = data[self._pos :].strip()
        self._pos = len(data)
        if not new:
            return []
        return [
            Event(kind="user", ts=_now(), summary=f"User inbox: {new[:80]}", data={"text": new}, relevance=0.8)
        ]


def default_roots() -> list[str]:
    roots_env = os.getenv("ZEUS_V4_WATCH_ROOTS", "").strip()
    if roots_env:
        return [r.strip() for r in roots_env.split(",") if r.strip()]
    return [os.getcwd()]
