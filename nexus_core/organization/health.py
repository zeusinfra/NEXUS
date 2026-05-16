from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus_core.organization.config import NexusOrgConfig, load_org_config


@dataclass(frozen=True)
class HealthReport:
    status: str
    pid: int | None
    pid_alive: bool
    heartbeat_age_s: float | None
    stale: bool
    mode: str
    agents: int
    tasks: int
    status_path: str
    pid_path: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_pid(path: Path, pid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid or os.getpid()), encoding="utf-8")


def clear_pid(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def read_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    return (Path("/proc") / str(pid)).exists()


def read_status_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_health_report(
    config: NexusOrgConfig | None = None,
    *,
    stale_after_s: float | None = None,
) -> HealthReport:
    config = config or load_org_config()
    status = read_status_file(config.daemon_status_path)
    pid = read_pid(config.daemon_pid_path)
    alive = pid_alive(pid)
    heartbeat = status.get("last_heartbeat")
    age = _heartbeat_age(heartbeat)
    stale_after = stale_after_s or max(15.0, config.heartbeat_interval_s * 3)
    stale = age is None or age > stale_after or not alive

    status_value = str(status.get("status") or "").lower()
    if not status:
        overall = "unknown"
        detail = "No daemon status file found."
    elif status_value == "stopped" and not alive:
        overall = "stopped"
        stale = False
        detail = "Daemon stopped cleanly and no PID is active."
    elif stale:
        overall = "stale"
        detail = "Daemon heartbeat is stale or PID is not alive."
    else:
        overall = "online"
        detail = "Daemon heartbeat and PID are healthy."

    return HealthReport(
        status=overall,
        pid=pid,
        pid_alive=alive,
        heartbeat_age_s=round(age, 3) if age is not None else None,
        stale=stale,
        mode=str(status.get("mode") or "UNKNOWN"),
        agents=int(status.get("agents") or 0),
        tasks=int(status.get("tasks") or 0),
        status_path=str(config.daemon_status_path),
        pid_path=str(config.daemon_pid_path),
        detail=detail,
    )


def render_systemd_user_unit(config: NexusOrgConfig | None = None) -> str:
    config = config or load_org_config()
    root = config.project_root
    python = root / ".venv" / "bin" / "python"
    python_cmd = python if python.exists() else "python3"
    log_path = config.logs_dir / "nexus_organization_systemd.log"
    return f"""[Unit]
Description=NEXUS Cognitive Company Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory={root}
ExecStart={python_cmd} -m nexus_core.organization run --config {root / "configs" / "nexus.toml"}
Environment="NEXUS_AUTONOMY_LEVEL=GUARDED"
Environment="NEXUS_EXECUTION_MODE=manual"
Environment="PYTHONIOENCODING=utf-8"
Environment="LC_ALL=C.UTF-8"
Environment="LANG=C.UTF-8"
Restart=on-failure
RestartSec=5
StandardOutput=append:{log_path}
StandardError=append:{log_path}

[Install]
WantedBy=default.target
"""


def install_instructions(config: NexusOrgConfig | None = None) -> dict[str, Any]:
    config = config or load_org_config()
    user_unit = (
        Path.home() / ".config" / "systemd" / "user" / "nexus-organization.service"
    )
    return {
        "unit_path": str(user_unit),
        "write_unit": f"mkdir -p {user_unit.parent} && ./bin/nexus org systemd-unit > {user_unit}",
        "reload": "systemctl --user daemon-reload",
        "enable": "systemctl --user enable nexus-organization.service",
        "start": "systemctl --user start nexus-organization.service",
        "status": "systemctl --user status nexus-organization.service",
        "health": "./bin/nexus org health",
        "note": "Review the rendered unit before enabling. This command set is not executed automatically.",
        "project_root": str(config.project_root),
    }


def systemd_plan(config: NexusOrgConfig | None = None) -> dict[str, Any]:
    config = config or load_org_config()
    instructions = install_instructions(config)
    return {
        "service": "nexus-organization.service",
        "unit_path": instructions["unit_path"],
        "unit_preview": render_systemd_user_unit(config),
        "commands": [
            instructions["write_unit"],
            instructions["reload"],
            instructions["enable"],
            instructions["start"],
            instructions["status"],
            instructions["health"],
        ],
        "requires_explicit_write": True,
        "requires_explicit_execute": True,
        "note": instructions["note"],
    }


def install_systemd_unit(
    config: NexusOrgConfig | None = None,
    *,
    write: bool = False,
    unit_path: Path | None = None,
) -> dict[str, Any]:
    config = config or load_org_config()
    target = unit_path or (
        Path.home() / ".config" / "systemd" / "user" / "nexus-organization.service"
    )
    unit = render_systemd_user_unit(config)
    if not write:
        return {
            "ok": False,
            "dry_run": True,
            "unit_path": str(target),
            "unit_preview": unit,
            "message": "Dry run only. Pass --write to write the user systemd unit.",
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(unit, encoding="utf-8")
    return {
        "ok": True,
        "dry_run": False,
        "unit_path": str(target),
        "message": "Unit file written. Run daemon-reload/enable/start explicitly.",
    }


def systemd_control(
    action: str,
    *,
    execute: bool = False,
    service: str = "nexus-organization.service",
    timeout_s: int = 15,
) -> dict[str, Any]:
    allowed = {
        "daemon-reload",
        "enable",
        "disable",
        "start",
        "stop",
        "restart",
        "status",
    }
    if action not in allowed:
        raise ValueError(f"Unsupported systemd action: {action}")
    command = ["systemctl", "--user"]
    if action != "daemon-reload":
        command.extend([action, service])
    else:
        command.append(action)
    if not execute:
        return {
            "ok": False,
            "dry_run": True,
            "command": command,
            "message": "Dry run only. Pass --execute to run this systemctl command.",
        }
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "dry_run": False,
        "command": command,
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
    }


def _heartbeat_age(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds()
