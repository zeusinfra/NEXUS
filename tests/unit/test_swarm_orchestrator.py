from __future__ import annotations

from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.daemon import OrganizationalDaemon


def test_swarm_orchestrator_creates_traceable_plan(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    daemon = OrganizationalDaemon(config)
    daemon.initialize()

    result = daemon.submit_swarm_objective(
        "Transformar o NEXUS em arquitetura swarm multiagente com runtime Linux",
        requested_by="tester",
        autonomy_level="LEVEL_1",
    )

    assert result["status"] == "planned"
    assert result["objective_id"].startswith("obj_")
    assert len(result["plan"]) >= 6
    assert {item["owner"] for item in result["plan"]} >= {
        "ceo",
        "planner",
        "security",
        "memory",
        "observer",
        "devops",
        "cto",
    }
    assert all(
        task["metadata"]["objective_id"] == result["objective_id"]
        for task in result["tasks"]
    )

    status = daemon.swarm.status()
    assert status["current_goal"] == result["goal"]
    assert status["memory"]["agents"] >= 7
    assert status["memory"]["tasks"] >= len(result["tasks"])
    assert status["memory"]["memory_entries"] >= 2
    entries = daemon.memory.list_memory_entries(limit=10)
    assert any(
        entry["scope"] == "swarm"
        and entry["kind"] == "objective"
        and entry["metadata"]["objective_id"] == result["objective_id"]
        for entry in entries
    )
    assert daemon.memory.list_agents(role="planner")[0]["status"] == "assigned"


def test_swarm_status_is_read_only_snapshot(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    daemon = OrganizationalDaemon(config)
    daemon.initialize()

    status = daemon.swarm.status()

    assert status["current_goal"] is None
    assert isinstance(status["agents"], list)
    assert "memory" in status
