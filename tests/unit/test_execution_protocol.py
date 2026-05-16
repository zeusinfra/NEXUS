from pathlib import Path

import pytest

from nexus_core.execution_protocol import (
    ActionState,
    ApprovalScope,
    ExecutionLedger,
    assert_verified_completion,
    build_sandbox_invocation,
    cancel_execution,
    command_hash,
    create_command_proposal,
    execute_approved_command,
    guard_agent_claim,
    read_execution_result,
    request_user_approval,
)
from nexus_core.tools import ToolError


@pytest.fixture
def execution_env(tmp_path, monkeypatch):
    ledger_path = tmp_path / "logs" / "execution_ledger.jsonl"
    artifact_dir = tmp_path / "logs" / "executions"
    monkeypatch.setenv("NEXUS_EXECUTION_LEDGER_PATH", str(ledger_path))
    monkeypatch.setenv("NEXUS_EXECUTION_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("NEXUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "python3")
    monkeypatch.setenv("NEXUS_EXECUTION_MODE", "manual")
    return tmp_path


def test_ledger_records_proposed_state(execution_env):
    proposal = create_command_proposal("python3 --version", cwd=str(execution_env))

    assert proposal["status"] == ActionState.PROPOSED.value
    assert proposal["proposal_id"]
    assert proposal["command_hash"] == command_hash(
        "python3 --version", str(execution_env)
    )

    latest = ExecutionLedger().latest(proposal["proposal_id"])
    assert latest["status"] == ActionState.PROPOSED.value


def test_state_machine_rejects_skipped_success(execution_env):
    ledger = ExecutionLedger()
    with pytest.raises(ToolError, match="Transição inválida"):
        ledger.transition(ActionState.PROPOSED.value, ActionState.SUCCEEDED.value)


def test_blocked_proposal_keeps_auditable_state_path(execution_env, monkeypatch):
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "python3")
    proposal = create_command_proposal("git status", cwd=str(execution_env))

    assert proposal["status"] == ActionState.BLOCKED.value
    states = [
        row["status"]
        for row in ExecutionLedger().records()
        if row["proposal_id"] == proposal["proposal_id"]
    ]
    assert states == [
        ActionState.DRAFT.value,
        ActionState.PROPOSED.value,
        ActionState.BLOCKED.value,
    ]


@pytest.mark.asyncio
async def test_pending_proposal_can_be_cancelled(execution_env):
    proposal = create_command_proposal("python3 --version", cwd=str(execution_env))

    cancelled = await cancel_execution(proposal["proposal_id"], reason="rejected")

    assert cancelled["status"] == ActionState.CANCELLED.value
    assert cancelled["verified_by_executor"] is True


@pytest.mark.asyncio
async def test_execute_requires_valid_approval_id(execution_env):
    proposal = create_command_proposal("python3 --version", cwd=str(execution_env))

    with pytest.raises(ToolError, match="not approved|current status"):
        await execute_approved_command(proposal["proposal_id"], "appr_invalid")


def test_approval_is_bound_to_command_hash(execution_env):
    proposal = create_command_proposal("python3 --version", cwd=str(execution_env))

    with pytest.raises(ToolError, match="invalidated"):
        request_user_approval(
            proposal["proposal_id"],
            approved_by="tester",
            command="python3 -V",
            cwd=str(execution_env),
        )


@pytest.mark.asyncio
async def test_stdout_and_stderr_are_captured(execution_env):
    script = execution_env / "io_case.py"
    script.write_text(
        'import sys\nprint("out")\nprint("err", file=sys.stderr)\n',
        encoding="utf-8",
    )
    command = f"python3 {script}"
    proposal = create_command_proposal(command, cwd=str(execution_env))
    approval = request_user_approval(proposal["proposal_id"], approved_by="tester")

    execution = await execute_approved_command(
        proposal["proposal_id"], approval["approval_id"], timeout_s=5
    )
    result = read_execution_result(proposal["proposal_id"])

    assert execution["status"] == ActionState.SUCCEEDED.value
    assert execution["exit_code"] == 0
    assert execution["verified_by_executor"] is True
    assert "out" in result["stdout"]
    assert "err" in result["stderr"]
    assert Path(execution["stdout_path"]).exists()
    assert Path(execution["stderr_path"]).exists()


@pytest.mark.asyncio
async def test_failed_command_is_not_marked_success(execution_env):
    script = execution_env / "fail_case.py"
    script.write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
    proposal = create_command_proposal(f"python3 {script}", cwd=str(execution_env))
    approval = request_user_approval(proposal["proposal_id"], approved_by="tester")

    execution = await execute_approved_command(
        proposal["proposal_id"], approval["approval_id"], timeout_s=5
    )

    assert execution["status"] == ActionState.FAILED.value
    assert execution["exit_code"] == 7
    with pytest.raises(ToolError):
        assert_verified_completion(proposal["proposal_id"])


@pytest.mark.asyncio
async def test_timeout_cancels_process(execution_env):
    script = execution_env / "timeout_case.py"
    script.write_text("import time\ntime.sleep(3)\n", encoding="utf-8")
    proposal = create_command_proposal(f"python3 {script}", cwd=str(execution_env))
    approval = request_user_approval(proposal["proposal_id"], approved_by="tester")

    execution = await execute_approved_command(
        proposal["proposal_id"], approval["approval_id"], timeout_s=1
    )

    assert execution["status"] == ActionState.CANCELLED.value
    assert execution["verified_by_executor"] is True


def test_no_fake_completion_without_ledger(execution_env):
    assert (
        guard_agent_claim("feito")
        == "Ainda não executei. Preciso criar uma proposta de comando para aprovação."
    )


def test_no_fake_completion_without_exit_code_zero(execution_env):
    proposal = create_command_proposal("python3 --version", cwd=str(execution_env))
    assert (
        guard_agent_claim("concluído", proposal_id=proposal["proposal_id"])
        == "Ainda não executei. Preciso criar uma proposta de comando para aprovação."
    )


def test_sandbox_invocation_mounts_cwd_and_maps_local_paths(
    execution_env, monkeypatch, tmp_path
):
    fake_engine_dir = tmp_path / "bin"
    fake_engine_dir.mkdir()
    fake_podman = fake_engine_dir / "podman"
    fake_podman.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_podman.chmod(0o755)
    script = execution_env / "script.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(fake_engine_dir))
    monkeypatch.setenv("NEXUS_EXECUTION_SANDBOX", "1")
    monkeypatch.setenv("NEXUS_SANDBOX_ENGINE", "podman")
    monkeypatch.setenv("NEXUS_SANDBOX_IMAGE", "python:3.12-slim")

    invocation = build_sandbox_invocation(["python3", str(script)], str(execution_env))

    assert invocation.enabled is True
    assert invocation.engine == "podman"
    assert invocation.tokens[:2] == ["podman", "run"]
    assert "--network" in invocation.tokens
    assert "none" in invocation.tokens
    assert f"{execution_env}:/workspace:rw" in invocation.tokens
    assert "/workspace/script.py" in invocation.tokens


@pytest.mark.asyncio
async def test_sandbox_request_blocks_when_engine_is_missing(
    execution_env, monkeypatch
):
    monkeypatch.setenv("NEXUS_EXECUTION_SANDBOX", "1")
    monkeypatch.setenv("NEXUS_SANDBOX_ENGINE", "nexus-missing-engine")
    proposal = create_command_proposal("python3 --version", cwd=str(execution_env))
    approval = request_user_approval(proposal["proposal_id"], approved_by="tester")

    execution = await execute_approved_command(
        proposal["proposal_id"], approval["approval_id"], timeout_s=5
    )

    assert execution["status"] == ActionState.BLOCKED.value
    assert "nexus-missing-engine is not available" in execution["summary"]
    assert execution["verified_by_executor"] is True


@pytest.mark.asyncio
async def test_dry_run_never_executes_command(execution_env, monkeypatch):
    marker = execution_env / "marker"
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "touch")
    monkeypatch.setenv("NEXUS_EXECUTION_MODE", "dry_run")
    proposal = create_command_proposal(f"touch {marker}", cwd=str(execution_env))
    approval = request_user_approval(proposal["proposal_id"], approved_by="tester")

    execution = await execute_approved_command(
        proposal["proposal_id"], approval["approval_id"], timeout_s=5
    )

    assert execution["status"] == ActionState.BLOCKED.value
    assert "Dry run" in execution["summary"]
    assert not marker.exists()


@pytest.mark.asyncio
async def test_disabled_mode_blocks_real_execution(execution_env, monkeypatch):
    marker = execution_env / "marker"
    monkeypatch.setenv("NEXUS_CMD_ALLOWLIST", "touch")
    monkeypatch.setenv("NEXUS_EXECUTION_MODE", "disabled")
    proposal = create_command_proposal(f"touch {marker}", cwd=str(execution_env))
    approval = request_user_approval(proposal["proposal_id"], approved_by="tester")

    execution = await execute_approved_command(
        proposal["proposal_id"], approval["approval_id"], timeout_s=5
    )

    assert execution["status"] == ActionState.BLOCKED.value
    assert "disabled" in execution["summary"]
    assert not marker.exists()


@pytest.mark.asyncio
async def test_session_low_risk_grant_auto_approves_low_risk_commands(
    execution_env, monkeypatch
):
    monkeypatch.setenv("NEXUS_EXECUTION_MODE", "session_low_risk")
    first = create_command_proposal("python3 --version", cwd=str(execution_env))
    request_user_approval(
        first["proposal_id"],
        approved_by="tester",
        approval_scope=ApprovalScope.SESSION_LOW_RISK,
    )

    second = create_command_proposal("python3 -V", cwd=str(execution_env))

    assert second["status"] == ActionState.APPROVED.value
    assert second["approval_id"]
    assert second["approval_scope"] == ApprovalScope.SESSION_LOW_RISK.value
    execution = await execute_approved_command(
        second["proposal_id"], second["approval_id"], timeout_s=5
    )
    assert execution["status"] == ActionState.SUCCEEDED.value
