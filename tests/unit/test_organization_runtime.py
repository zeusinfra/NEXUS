from __future__ import annotations

import pytest

from nexus_core.execution_protocol import ActionState
from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.daemon import OrganizationalDaemon
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.organization.verification import VerificationEngine
from nexus_core.tools import ToolError


@pytest.fixture
def runtime_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "NEXUS_EXECUTION_LEDGER_PATH", str(tmp_path / "logs" / "ledger.jsonl")
    )
    monkeypatch.setenv(
        "NEXUS_EXECUTION_ARTIFACT_DIR", str(tmp_path / "logs" / "executions")
    )
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "python3")
    monkeypatch.setenv("NEXUS_EXECUTION_MODE", "manual")
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    daemon = OrganizationalDaemon(config)
    daemon.initialize()
    return daemon


@pytest.mark.asyncio
async def test_runtime_executes_approved_command_with_evidence(runtime_daemon):
    item = runtime_daemon.propose_command("python3 --version", requested_by="tester")
    runtime_daemon.permissions.approve_command(
        item["proposal_id"], approved_by="tester"
    )

    result = await runtime_daemon.runtime.execute_approved(
        item["proposal_id"], agent="devops", timeout_s=5
    )

    assert result["command_id"].startswith("cmd_")
    assert result["status"] == "executed"
    assert result["execution"]["status"] == ActionState.SUCCEEDED.value
    assert result["verification"]["status"] == "passed"
    assert result["execution"]["verified_by_executor"] is True
    assert result["execution_plan"]["status"] == "completed"
    assert result["resource_budget"]["allowed"] is True
    assert result["replay"]["target_id"] == result["command_id"]
    assert result["runtime_events"]

    command_id = result["command_id"]
    event_types = {
        event["event_type"]
        for event in runtime_daemon.memory.list_runtime_events(command_id=command_id)
    }
    assert "COMMAND_STARTED" in event_types
    assert "EXECUTION_OUTPUT" in event_types
    assert "COMMAND_FINISHED" in event_types
    assert (
        runtime_daemon.memory.list_verifications(command_id=command_id)[0]["status"]
        == "passed"
    )
    assert (
        runtime_daemon.memory.list_commands(status="executed")[0]["command_id"]
        == command_id
    )
    assert (
        runtime_daemon.memory.list_approvals(status="executed")[0]["proposal_id"]
        == item["proposal_id"]
    )
    assert runtime_daemon.memory.list_execution_plans(command_id=command_id)
    step_statuses = {
        step["action_type"]: step["status"]
        for step in runtime_daemon.memory.list_execution_steps(command_id=command_id)
    }
    assert step_statuses["command_execution"] == "passed"
    assert step_statuses["verification"] == "passed"
    replay = runtime_daemon.replay_command(command_id)
    replay_types = {entry["type"] for entry in replay["timeline"]}
    assert {"plan_step", "runtime_event", "verification"}.issubset(replay_types)


@pytest.mark.asyncio
async def test_runtime_refuses_unapproved_command(runtime_daemon):
    item = runtime_daemon.propose_command("python3 --version", requested_by="tester")

    with pytest.raises(ToolError, match="not approved|approval_id"):
        await runtime_daemon.runtime.execute_approved(item["proposal_id"])


@pytest.mark.asyncio
async def test_runtime_records_failed_verification(runtime_daemon, tmp_path):
    script = tmp_path / "fail.py"
    script.write_text("import sys\nsys.exit(9)\n", encoding="utf-8")
    item = runtime_daemon.propose_command(f"python3 {script}", requested_by="tester")
    runtime_daemon.permissions.approve_command(
        item["proposal_id"], approved_by="tester"
    )

    result = await runtime_daemon.runtime.execute_approved(
        item["proposal_id"], agent="reviewer", timeout_s=5
    )

    assert result["status"] == "failed"
    assert result["execution"]["status"] == ActionState.FAILED.value
    assert result["execution"]["exit_code"] == 9
    assert result["verification"]["status"] == "failed"
    assert result["execution_plan"]["status"] == "failed"
    assert result["self_healing"]["status"] == "diagnosed"
    assert (
        runtime_daemon.memory.list_incidents()[0]["command_id"] == result["command_id"]
    )
    event_types = {
        event["event_type"]
        for event in runtime_daemon.memory.list_runtime_events(
            command_id=result["command_id"]
        )
    }
    assert "SELF_HEALING_DIAGNOSTIC" in event_types


def test_verification_engine_detects_file_changes(tmp_path):
    store = OrganizationalMemoryStore(tmp_path / "org.sqlite3")
    verifier = VerificationEngine(store)
    target = tmp_path / "state.txt"
    before = verifier.fingerprint_file(target)

    target.write_text("changed", encoding="utf-8")
    result = verifier.verify_file_changed(target, before=before, command_id="cmd_test")

    assert result["status"] == "passed"
    assert store.list_verifications(command_id="cmd_test")[0]["target_type"] == "file"
