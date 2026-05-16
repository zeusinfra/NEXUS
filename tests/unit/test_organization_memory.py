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
