from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable

import psutil
from nexus_core.organization.memory import OrganizationalMemoryStore


@dataclass(frozen=True)
class ObservationSnapshot:
    mode: str
    confidence: float
    active_window: str | None
    system: dict[str, Any]
    processes: list[dict[str, Any]]
    triggers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ObserverEngine:
    """Lightweight Linux context observer for the organizational daemon."""

    def __init__(
        self,
        *,
        memory: OrganizationalMemoryStore | None = None,
        attention: Any | None = None,
        process_provider: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.memory = memory
        self.attention = attention or LocalAttentionProbe()
        self.process_provider = process_provider or self._top_processes

    def observe(self) -> ObservationSnapshot:
        attention_snapshot = self.attention.get_current_attention()
        system = self._system_snapshot()
        processes = self.process_provider()
        mode, confidence, triggers = self._classify(
            attention_snapshot.to_dict(), system, processes
        )
        snapshot = ObservationSnapshot(
            mode=mode,
            confidence=confidence,
            active_window=attention_snapshot.active_window,
            system=system,
            processes=processes,
            triggers=[*attention_snapshot.triggers, *triggers],
        )
        if self.memory:
            self.memory.record_observation(snapshot.to_dict())
        return snapshot

    def _classify(
        self,
        attention: dict[str, Any],
        system: dict[str, Any],
        processes: list[dict[str, Any]],
    ) -> tuple[str, float, list[str]]:
        triggers: list[str] = []
        state = str(attention.get("state") or "idle").upper()
        active_window = str(attention.get("active_window") or "").lower()
        names = " ".join(str(p.get("name") or "").lower() for p in processes)

        if system.get("cpu_percent", 0) > 85 or system.get("ram_percent", 0) > 90:
            triggers.append("High resource pressure detected")
            return "MAINTENANCE", 0.85, triggers
        if state in {"DEEP_FOCUS", "DEBUGGING"}:
            return "DEEP_WORK", 0.86, triggers
        if state == "DEVELOPMENT" or _contains_any(
            active_window + " " + names,
            ["code", "vscode", "terminal", "git", "cargo", "pytest", "rust", "python"],
        ):
            triggers.append("Development tools detected")
            return "DEVELOPMENT", 0.82, triggers
        if state == "RESEARCH" or _contains_any(
            active_window + " " + names,
            ["firefox", "chrome", "brave", "pdf", "arxiv", "documentation"],
        ):
            triggers.append("Research tools detected")
            return "RESEARCH", 0.74, triggers
        return "IDLE", 0.55, triggers

    def _system_snapshot(self) -> dict[str, Any]:
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }

    def _top_processes(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            for proc in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_percent"]
            ):
                try:
                    info = proc.info
                    rows.append(
                        {
                            "pid": info.get("pid"),
                            "name": info.get("name") or "",
                            "cpu_percent": round(
                                float(info.get("cpu_percent") or 0.0), 2
                            ),
                            "memory_percent": round(
                                float(info.get("memory_percent") or 0.0), 2
                            ),
                        }
                    )
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
        except Exception:
            return []
        return sorted(
            rows,
            key=lambda row: (row["cpu_percent"], row["memory_percent"]),
            reverse=True,
        )[:8]


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


class LocalAttentionSnapshot:
    def __init__(
        self, *, state: str, active_window: str | None, triggers: list[str]
    ) -> None:
        self.state = state
        self.active_window = active_window
        self.triggers = triggers

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "active_window": self.active_window,
            "triggers": self.triggers,
        }


class LocalAttentionProbe:
    """Small no-LLM active-window probe to keep org CLI JSON clean."""

    def get_current_attention(self) -> LocalAttentionSnapshot:
        active_window = self._active_window_title()
        return LocalAttentionSnapshot(
            state="idle",
            active_window=active_window,
            triggers=[],
        )

    def _active_window_title(self) -> str | None:
        import re
        import subprocess

        try:
            out_id = subprocess.check_output(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"], stderr=subprocess.DEVNULL
            ).decode()
            match = re.search(r"window id # (0x[0-9a-f]+)", out_id)
            if not match:
                return None
            win_id = match.group(1)
            out_list = subprocess.check_output(
                ["wmctrl", "-lp"], stderr=subprocess.DEVNULL
            ).decode()
            for line in out_list.splitlines():
                if win_id.lower() in line.lower():
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        return parts[4]
        except Exception:
            return None
        return None
