from __future__ import annotations

from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.daemon import OrganizationalDaemon
from nexus_core.organization.memory import OrganizationalMemoryStore


def test_memory_store_persists_tasks_decisions_events_and_summaries(tmp_path):
    store = OrganizationalMemoryStore(tmp_path / "org.sqlite3")
    blackboard = Blackboard(tmp_path / "blackboard.json", memory=store)

    task = blackboard.create_task(
        "Criar memória organizacional",
        owner="memory",
        goal="Persistir decisões e tarefas",
    )
    decision = blackboard.record_decision(
        "Usar SQLite para histórico",
        "SQLite é leve e local para a Fase 3.",
        owner="cto",
    )
    blackboard.append_event("ORG_TEST_EVENT", {"task_id": task["id"]})
    summary = store.create_summary(scope="test")

    reloaded = OrganizationalMemoryStore(tmp_path / "org.sqlite3")
    assert reloaded.list_tasks()[0]["id"] == task["id"]
    assert reloaded.list_decisions()[0]["id"] == decision["id"]
    assert (
        reloaded.list_events(event_type="ORG_TEST_EVENT")[0]["payload"]["task_id"]
        == task["id"]
    )
    assert reloaded.list_summaries(scope="test")[0]["id"] == summary["id"]


def test_daemon_wires_blackboard_to_memory(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    daemon = OrganizationalDaemon(config)

    daemon.initialize()
    result = daemon.submit_goal("registrar decisão de arquitetura", role="cto")
    summary = daemon.summarize_memory(scope="daemon-test")
    counts = daemon.memory_status()

    assert result.task_id
    assert counts["tasks"] >= 1
    assert counts["events"] >= 2
    assert counts["summaries"] == 1
    assert "Organizational memory snapshot" in summary["summary"]


def test_task_updates_are_reflected_in_memory(tmp_path):
    store = OrganizationalMemoryStore(tmp_path / "org.sqlite3")
    blackboard = Blackboard(tmp_path / "blackboard.json", memory=store)
    task = blackboard.create_task("Validar atualização", owner="reviewer")

    blackboard.update_task(task["id"], status="done")

    tasks = store.list_tasks(status="done")
    assert len(tasks) == 1
    assert tasks[0]["id"] == task["id"]


def test_memory_store_persists_swarm_runtime_tables(tmp_path):
    store = OrganizationalMemoryStore(tmp_path / "org.sqlite3")

    agent = store.record_agent_state(
        agent_id="agent_coder",
        role="coder",
        status="assigned",
        current_task="task_1",
        confidence=0.8,
        risk_level="medium",
        permissions=["coding"],
        memory_scope="engineering",
    )
    command = store.record_command(
        {
            "command_id": "cmd_1",
            "agent_id": "agent_coder",
            "task_id": "task_1",
            "proposal_id": "prop_1",
            "command": "python3 --version",
            "cwd": str(tmp_path),
            "status": "running",
        }
    )
    store.record_command({**command, "status": "executed", "exit_code": 0})
    incident = store.record_incident(
        severity="error",
        module="runtime",
        message="failed",
        agent_id="agent_coder",
        command_id="cmd_1",
    )
    approval = store.record_approval(
        {
            "proposal_id": "prop_1",
            "command": "python3 --version",
            "cwd": str(tmp_path),
            "status": "pending_approval",
            "requested_by": "tester",
            "risk_level": "LOW",
        }
    )
    entry = store.record_memory_entry(
        scope="swarm",
        kind="lesson",
        content="Verify before saying done.",
        source="test",
    )

    assert store.list_agents(role="coder")[0]["agent_id"] == agent["agent_id"]
    assert store.list_commands(status="executed")[0]["command_id"] == "cmd_1"
    assert store.list_incidents()[0]["id"] == incident["id"]
    assert (
        store.list_approvals(status="pending_approval")[0]["proposal_id"]
        == approval["proposal_id"]
    )
    assert store.list_memory_entries(scope="swarm")[0]["id"] == entry["id"]
    counts = store.counts()
    assert counts["agents"] == 1
    assert counts["commands"] == 1
    assert counts["incidents"] == 1
    assert counts["approvals"] == 1
    assert counts["memory_entries"] == 1
