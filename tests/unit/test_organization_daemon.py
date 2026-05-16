from __future__ import annotations

import json

from nexus_core.organization.agents import build_default_registry
from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.daemon import OrganizationalDaemon


def test_blackboard_persists_agents_tasks_and_decisions(tmp_path):
    board_path = tmp_path / "runtime" / "state" / "blackboard.json"
    blackboard = Blackboard(board_path)
    registry = build_default_registry()

    registry.sync_blackboard(blackboard)
    task = blackboard.create_task("Implementar base organizacional", owner="planner")
    decision = blackboard.record_decision(
        "Usar daemon incremental",
        "Evita reescrita ampla e preserva execution_protocol existente.",
        owner="cto",
    )

    reloaded = Blackboard(board_path).snapshot()
    assert "ceo" in reloaded["agents"]
    assert reloaded["tasks"][task["id"]]["owner"] == "planner"
    assert reloaded["decisions"][0]["id"] == decision["id"]


def test_registry_routes_goals_to_specialized_agents(tmp_path):
    blackboard = Blackboard(tmp_path / "blackboard.json")
    registry = build_default_registry()
    registry.sync_blackboard(blackboard)

    security = registry.dispatch("preciso alterar systemd com sudo", blackboard)
    coding = registry.dispatch("implementar codigo no layout rust", blackboard)
    default = registry.dispatch("organizar prioridades da semana", blackboard)

    assert security.agent_role in {"security", "devops"}
    assert coding.agent_role == "coder"
    assert default.agent_role == "ceo"


def test_daemon_initializes_runtime_and_status(tmp_path):
    config = NexusOrgConfig.from_mapping(
        {
            "project_root": str(tmp_path),
            "runtime": {
                "dir": "runtime",
                "state_dir": "runtime/state",
                "logs_dir": "logs",
            },
        }
    )
    daemon = OrganizationalDaemon(config)

    daemon.initialize()
    result = daemon.submit_goal("planejar empresa cognitiva", role="planner")
    status = daemon.status()

    assert result.agent_role == "planner"
    assert status.agents == 9
    assert status.tasks == 1
    assert config.blackboard_path.exists()
    assert (tmp_path / "runtime" / "state").exists()

    with config.blackboard_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["tasks"][result.task_id]["owner"] == "planner"
