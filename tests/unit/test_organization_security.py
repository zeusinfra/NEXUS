from __future__ import annotations

import pytest

from nexus_core.execution_protocol import ActionState
from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.security import PermissionManager, PolicyEngine
from nexus_core.tools import ToolError


@pytest.fixture
def permission_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "NEXUS_EXECUTION_LEDGER_PATH", str(tmp_path / "logs" / "ledger.jsonl")
    )
    monkeypatch.setenv(
        "NEXUS_EXECUTION_ARTIFACT_DIR", str(tmp_path / "logs" / "executions")
    )
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "python3,touch,systemctl")
    monkeypatch.setenv("NEXUS_EXECUTION_MODE", "manual")
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    board = Blackboard(config.blackboard_path)
    return PermissionManager(config, board), config


def test_policy_assessment_marks_write_command_for_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "touch")
    assessment = PolicyEngine().assess_command("touch marker", cwd=str(tmp_path))

    assert assessment.risk_level == "MEDIUM"
    assert assessment.requires_approval is True
    assert assessment.dry_run_recommended is True


def test_permission_manager_queues_pending_command(permission_env):
    manager, _config = permission_env

    item = manager.propose_command("python3 --version", reason="check interpreter")

    assert item["status"] == "pending_approval"
    assert item["ledger_status"] == ActionState.PROPOSED.value
    assert item["proposal_id"]
    assert (
        manager.queue.list(status="pending_approval")[0]["proposal_id"]
        == item["proposal_id"]
    )


def test_blocked_command_is_visible_in_queue(permission_env, monkeypatch):
    manager, _config = permission_env
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "rm")

    item = manager.propose_command("rm something", reason="destructive test")

    assert item["status"] == "blocked"
    assert item["ledger_status"] == ActionState.BLOCKED.value
    assert "rm:" in item["assessment"]["warnings"][0]


def test_approval_updates_queue_without_execution(permission_env):
    manager, config = permission_env
    item = manager.propose_command("python3 --version")

    approved = manager.approve_command(item["proposal_id"], approved_by="tester")

    assert approved["status"] == "approved"
    assert approved["approval_id"]
    assert approved["approved_by"] == "tester"
    assert not (config.logs_dir / "executions").exists()


@pytest.mark.asyncio
async def test_execute_requires_approval(permission_env):
    manager, _config = permission_env
    item = manager.propose_command("python3 --version")

    with pytest.raises(ToolError, match="not approved|approval_id"):
        await manager.execute_command(item["proposal_id"])


@pytest.mark.asyncio
async def test_execute_after_approval_records_verified_result(permission_env):
    manager, _config = permission_env
    item = manager.propose_command("python3 --version")
    manager.approve_command(item["proposal_id"], approved_by="tester")

    result = await manager.execute_command(item["proposal_id"], timeout_s=5)

    assert result["status"] == "executed"
    assert result["execution"]["status"] == ActionState.SUCCEEDED.value
    assert result["execution"]["verified_by_executor"] is True
