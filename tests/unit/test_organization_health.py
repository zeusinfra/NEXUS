from __future__ import annotations

import json
import os

from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.health import (
    build_health_report,
    clear_pid,
    install_systemd_unit,
    install_instructions,
    render_systemd_user_unit,
    systemd_control,
    systemd_plan,
    write_pid,
)


def test_health_reports_online_for_fresh_heartbeat_and_live_pid(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    config.ensure_directories()
    write_pid(config.daemon_pid_path, os.getpid())
    config.daemon_status_path.write_text(
        json.dumps(
            {
                "status": "online",
                "mode": "DEVELOPMENT",
                "agents": 9,
                "tasks": 2,
                "last_heartbeat": "2999-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    report = build_health_report(config, stale_after_s=30)

    assert report.status == "online"
    assert report.pid_alive is True
    assert report.stale is False
    assert report.mode == "DEVELOPMENT"
    assert report.agents == 9


def test_health_reports_stale_without_pid(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    config.ensure_directories()
    clear_pid(config.daemon_pid_path)
    config.daemon_status_path.write_text(
        json.dumps(
            {
                "status": "online",
                "mode": "IDLE",
                "agents": 9,
                "tasks": 0,
                "last_heartbeat": "2000-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    report = build_health_report(config, stale_after_s=1)

    assert report.status == "stale"
    assert report.pid_alive is False
    assert report.stale is True


def test_health_reports_clean_stopped_state(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    config.ensure_directories()
    clear_pid(config.daemon_pid_path)
    config.daemon_status_path.write_text(
        json.dumps(
            {
                "status": "stopped",
                "mode": "IDLE",
                "agents": 9,
                "tasks": 0,
                "last_heartbeat": "2000-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    report = build_health_report(config, stale_after_s=1)

    assert report.status == "stopped"
    assert report.stale is False
    assert report.pid_alive is False


def test_rendered_systemd_unit_uses_current_project_paths(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})

    unit = render_systemd_user_unit(config)
    instructions = install_instructions(config)

    assert f"WorkingDirectory={tmp_path}" in unit
    assert "-m nexus_core.organization run" in unit
    assert str(tmp_path / "configs" / "nexus.toml") in unit
    assert instructions["health"] == "./bin/nexus org health"
    assert (
        "systemctl --user enable nexus-organization.service" in instructions["enable"]
    )


def test_systemd_plan_is_explicit_and_non_executing(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})

    plan = systemd_plan(config)

    assert plan["requires_explicit_write"] is True
    assert plan["requires_explicit_execute"] is True
    assert "systemctl --user start nexus-organization.service" in plan["commands"]
    assert "ExecStart=" in plan["unit_preview"]


def test_systemd_install_dry_run_does_not_write(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    target = tmp_path / "user" / "nexus-organization.service"

    result = install_systemd_unit(config, unit_path=target)

    assert result["dry_run"] is True
    assert result["ok"] is False
    assert not target.exists()


def test_systemd_install_write_is_explicit(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    target = tmp_path / "user" / "nexus-organization.service"

    result = install_systemd_unit(config, write=True, unit_path=target)

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert target.exists()
    assert "NEXUS Cognitive Company Daemon" in target.read_text(encoding="utf-8")


def test_systemd_control_dry_run_does_not_execute():
    result = systemd_control("start")

    assert result["dry_run"] is True
    assert result["ok"] is False
    assert result["command"] == [
        "systemctl",
        "--user",
        "start",
        "nexus-organization.service",
    ]
