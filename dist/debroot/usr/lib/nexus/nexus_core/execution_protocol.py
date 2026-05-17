from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import shlex
import signal
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable

from nexus_core.command_policy import classify_command, validate_command
from nexus_core.tools import ToolError


class ActionState(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = {
    ActionState.SUCCEEDED,
    ActionState.FAILED,
    ActionState.BLOCKED,
    ActionState.CANCELLED,
}

_RUNNING_PROCESSES: dict[str, asyncio.subprocess.Process] = {}
_CANCEL_REQUESTS: set[str] = set()

ALLOWED_TRANSITIONS = {
    ActionState.DRAFT: {ActionState.PROPOSED},
    ActionState.PROPOSED: {
        ActionState.APPROVED,
        ActionState.BLOCKED,
        ActionState.CANCELLED,
    },
    ActionState.APPROVED: {ActionState.QUEUED, ActionState.CANCELLED},
    ActionState.QUEUED: {
        ActionState.RUNNING,
        ActionState.CANCELLED,
        ActionState.BLOCKED,
    },
    ActionState.RUNNING: {
        ActionState.SUCCEEDED,
        ActionState.FAILED,
        ActionState.CANCELLED,
    },
    ActionState.SUCCEEDED: set(),
    ActionState.FAILED: set(),
    ActionState.BLOCKED: set(),
    ActionState.CANCELLED: set(),
}


class ApprovalScope(str, Enum):
    ONCE = "ONCE"
    SESSION_LOW_RISK = "SESSION_LOW_RISK"


class ExecutionMode(str, Enum):
    MANUAL = "manual"
    SESSION_LOW_RISK = "session_low_risk"
    DRY_RUN = "dry_run"
    DISABLED = "disabled"


@dataclass(frozen=True)
class SandboxInvocation:
    enabled: bool
    engine: str | None = None
    image: str = ""
    tokens: list[str] = field(default_factory=list)
    cwd: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def project_root() -> Path:
    env_root = os.getenv("NEXUS_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def ledger_path() -> Path:
    env_path = os.getenv("NEXUS_EXECUTION_LEDGER_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return project_root() / "logs" / "execution_ledger.jsonl"


def artifacts_dir() -> Path:
    env_path = os.getenv("NEXUS_EXECUTION_ARTIFACT_DIR", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return ledger_path().parent / "executions"


def command_hash(command: str, cwd: str) -> str:
    payload = json.dumps({"command": command, "cwd": cwd}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def execution_mode() -> ExecutionMode:
    raw = os.getenv("NEXUS_EXECUTION_MODE", ExecutionMode.MANUAL.value).strip().lower()
    try:
        return ExecutionMode(raw)
    except ValueError:
        return ExecutionMode.MANUAL


def sandbox_requested() -> bool:
    return os.getenv("NEXUS_EXECUTION_SANDBOX", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def build_sandbox_invocation(tokens: list[str], cwd: str) -> SandboxInvocation:
    if not sandbox_requested():
        return SandboxInvocation(enabled=False, tokens=tokens, cwd=cwd)

    preferred = os.getenv("NEXUS_SANDBOX_ENGINE", "auto").strip().lower() or "auto"
    candidates = ["podman", "docker"] if preferred == "auto" else [preferred]
    engine = next(
        (candidate for candidate in candidates if shutil.which(candidate)), None
    )
    if engine is None:
        raise ToolError(
            "Sandbox requested, but neither podman nor docker is available."
            if preferred == "auto"
            else f"Sandbox requested, but {preferred} is not available."
        )

    image = os.getenv("NEXUS_SANDBOX_IMAGE", "python:3.12-slim").strip()
    if not image:
        raise ToolError("NEXUS_SANDBOX_IMAGE is required when sandbox is enabled.")

    root = Path(cwd).expanduser().resolve()
    container_tokens = [_map_token_into_workspace(token, root) for token in tokens]
    network = os.getenv("NEXUS_SANDBOX_NETWORK", "none").strip() or "none"
    mount_mode = os.getenv("NEXUS_SANDBOX_MOUNT_MODE", "rw").strip().lower()
    if mount_mode not in {"ro", "rw"}:
        mount_mode = "rw"

    invocation = [
        engine,
        "run",
        "--rm",
        "--network",
        network,
        "--workdir",
        "/workspace",
        "--volume",
        f"{root}:/workspace:{mount_mode}",
    ]
    if os.getuid() != 0:
        invocation.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
    invocation.append(image)
    invocation.extend(container_tokens)
    return SandboxInvocation(
        enabled=True,
        engine=engine,
        image=image,
        tokens=invocation,
        cwd=str(root),
    )


def _map_token_into_workspace(token: str, root: Path) -> str:
    try:
        path = Path(token)
    except TypeError:
        return token
    if not path.is_absolute():
        return token
    try:
        rel = path.resolve().relative_to(root)
    except (OSError, ValueError):
        return token
    return str(Path("/workspace") / rel)


def risk_for_command(command: str) -> tuple[str, bool]:
    tokens = shlex.split(command)
    decision = classify_command(tokens)
    if decision.category == "read" and not decision.requires_confirmation:
        return "LOW", False
    if decision.category == "write":
        return "MEDIUM", True
    return "HIGH", True


@dataclass
class ExecutionRecord:
    proposal_id: str
    approval_id: str | None
    command: str
    cwd: str
    status: str
    pid: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    summary: str = ""
    verified_by_executor: bool = False
    command_hash: str = ""
    risk_level: str = "LOW"
    approved_by: str | None = None
    approval_scope: str | None = None
    expires_at: str | None = None
    event: str = "state"
    ts: str = field(default_factory=utc_now)


class ExecutionLedger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ledger_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: ExecutionRecord) -> dict:
        payload = asdict(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def latest(self, proposal_id: str) -> dict | None:
        current = None
        for row in self.records():
            if row.get("proposal_id") == proposal_id:
                current = row
        return current

    def transition(self, previous: str, next_status: str) -> None:
        prev = ActionState(previous)
        nxt = ActionState(next_status)
        if nxt not in ALLOWED_TRANSITIONS[prev]:
            raise ToolError(f"Transição inválida: {previous} -> {next_status}")

    def append_transition(self, previous: str, record: ExecutionRecord) -> dict:
        self.transition(previous, record.status)
        return self.append(record)


def get_execution_status(proposal_id: str) -> dict | None:
    return ExecutionLedger().latest(proposal_id)


def read_execution_result(proposal_id: str) -> dict:
    row = get_execution_status(proposal_id)
    if not row:
        raise ToolError("Execução não encontrada no ledger.")

    result = dict(row)
    for key in ("stdout_path", "stderr_path"):
        path = row.get(key)
        if path and Path(path).exists():
            result[key.replace("_path", "")] = Path(path).read_text(
                encoding="utf-8", errors="replace"
            )[-50_000:]
        else:
            result[key.replace("_path", "")] = ""
    return result


def _active_session_low_risk_grant(ledger: ExecutionLedger) -> dict | None:
    now = datetime.now(timezone.utc)
    for row in reversed(ledger.records()):
        if row.get("status") != ActionState.APPROVED.value:
            continue
        if row.get("approval_scope") != ApprovalScope.SESSION_LOW_RISK.value:
            continue
        if row.get("risk_level") != "LOW":
            continue
        expires_at = row.get("expires_at")
        if expires_at and parse_utc(expires_at) <= now:
            continue
        return row
    return None


def create_command_proposal(
    command: str,
    *,
    cwd: str | None = None,
    reason: str = "",
    ledger: ExecutionLedger | None = None,
) -> dict:
    ledger = ledger or ExecutionLedger()
    command = str(command or "").strip()
    if not command:
        raise ToolError("command is required.")
    cwd = str(Path(cwd or project_root()).expanduser().resolve())
    proposal_id = f"prop_{uuid.uuid4().hex[:16]}"
    base = {
        "proposal_id": proposal_id,
        "approval_id": None,
        "command": command,
        "cwd": cwd,
        "command_hash": command_hash(command, cwd),
    }
    ledger.append(
        ExecutionRecord(
            **base,
            status=ActionState.DRAFT.value,
            summary="Draft command proposal created.",
            verified_by_executor=False,
        )
    )
    tokens = shlex.split(command)
    try:
        decision = validate_command(command, tokens, confirmed=True)
        risk_level = "LOW" if decision.category == "read" else "MEDIUM"
    except ToolError as exc:
        record = ExecutionRecord(
            **base,
            status=ActionState.PROPOSED.value,
            risk_level="HIGH",
            summary=reason or "Command proposal created.",
            verified_by_executor=False,
        )
        ledger.append_transition(ActionState.DRAFT.value, record)
        blocked = ExecutionRecord(
            **base,
            status=ActionState.BLOCKED.value,
            risk_level="HIGH",
            summary=f"Blocked by policy: {exc}",
            verified_by_executor=True,
        )
        return ledger.append_transition(ActionState.PROPOSED.value, blocked)

    record = ExecutionRecord(
        **base,
        status=ActionState.PROPOSED.value,
        risk_level=risk_level,
        summary=reason or "Command proposal created.",
        verified_by_executor=False,
    )
    proposal = ledger.append_transition(ActionState.DRAFT.value, record)
    if execution_mode() == ExecutionMode.SESSION_LOW_RISK and risk_level == "LOW":
        grant = _active_session_low_risk_grant(ledger)
        if grant:
            approval = ExecutionRecord(
                proposal_id=proposal_id,
                approval_id=f"appr_{uuid.uuid4().hex[:16]}",
                command=command,
                cwd=cwd,
                status=ActionState.APPROVED.value,
                command_hash=base["command_hash"],
                risk_level=risk_level,
                approved_by=grant.get("approved_by") or "session_low_risk",
                approval_scope=ApprovalScope.SESSION_LOW_RISK.value,
                expires_at=grant.get("expires_at"),
                summary="Approved by active session low-risk grant.",
                verified_by_executor=False,
            )
            return ledger.append_transition(ActionState.PROPOSED.value, approval)
    return proposal


def request_user_approval(
    proposal_id: str,
    *,
    approved_by: str,
    approval_scope: ApprovalScope = ApprovalScope.ONCE,
    ttl_seconds: int = 600,
    command: str | None = None,
    cwd: str | None = None,
    ledger: ExecutionLedger | None = None,
) -> dict:
    ledger = ledger or ExecutionLedger()
    current = ledger.latest(proposal_id)
    if not current:
        raise ToolError("Proposal not found.")
    if current["status"] != ActionState.PROPOSED.value:
        raise ToolError(f"Proposal is not approvable in status {current['status']}.")

    command = command if command is not None else current["command"]
    cwd = cwd if cwd is not None else current["cwd"]
    if command_hash(command, cwd) != current["command_hash"]:
        raise ToolError("Approval invalidated: command or cwd changed.")

    expires_at = (
        (datetime.now(timezone.utc) + timedelta(seconds=max(1, ttl_seconds)))
        .isoformat()
        .replace("+00:00", "Z")
    )
    approval_id = f"appr_{uuid.uuid4().hex[:16]}"
    record = ExecutionRecord(
        proposal_id=proposal_id,
        approval_id=approval_id,
        command=current["command"],
        cwd=current["cwd"],
        status=ActionState.APPROVED.value,
        command_hash=current["command_hash"],
        risk_level=current["risk_level"],
        approved_by=approved_by,
        approval_scope=approval_scope.value,
        expires_at=expires_at,
        summary="Approved by user.",
        verified_by_executor=False,
    )
    return ledger.append(record)


def _assert_approval_valid(
    proposal_id: str,
    approval_id: str,
    command: str,
    cwd: str,
    *,
    ledger: ExecutionLedger,
) -> dict:
    current = ledger.latest(proposal_id)
    if not current:
        raise ToolError("Proposal not found.")
    if current["status"] != ActionState.APPROVED.value:
        raise ToolError(
            f"Command is not approved; current status is {current['status']}."
        )
    if current.get("approval_id") != approval_id:
        raise ToolError("Invalid approval_id for proposal.")
    if command_hash(command, cwd) != current["command_hash"]:
        raise ToolError("Approval invalidated: command or cwd changed.")
    expires_at = current.get("expires_at")
    if expires_at and parse_utc(expires_at) <= datetime.now(timezone.utc):
        raise ToolError("Approval expired.")
    return current


async def execute_approved_command(
    proposal_id: str,
    approval_id: str,
    *,
    timeout_s: int = 30,
    on_event: Callable[[dict], Awaitable[None]] | None = None,
    ledger: ExecutionLedger | None = None,
) -> dict:
    ledger = ledger or ExecutionLedger()
    current = ledger.latest(proposal_id)
    if not current:
        raise ToolError("Proposal not found.")
    command = current["command"]
    cwd = current["cwd"]
    approval = _assert_approval_valid(
        proposal_id, approval_id, command, cwd, ledger=ledger
    )

    mode = execution_mode()
    if mode == ExecutionMode.DISABLED:
        queued = ExecutionRecord(
            proposal_id=proposal_id,
            approval_id=approval_id,
            command=command,
            cwd=cwd,
            status=ActionState.QUEUED.value,
            command_hash=current["command_hash"],
            risk_level=current["risk_level"],
            approved_by=approval.get("approved_by"),
            approval_scope=approval.get("approval_scope"),
            expires_at=approval.get("expires_at"),
            summary="Queued for execution mode check.",
        )
        ledger.append_transition(ActionState.APPROVED.value, queued)
        return ledger.append_transition(
            ActionState.QUEUED.value,
            ExecutionRecord(
                proposal_id=proposal_id,
                approval_id=approval_id,
                command=command,
                cwd=cwd,
                status=ActionState.BLOCKED.value,
                command_hash=current["command_hash"],
                risk_level=current["risk_level"],
                summary="Execution disabled by NEXUS_EXECUTION_MODE=disabled.",
                verified_by_executor=True,
            ),
        )
    if mode == ExecutionMode.DRY_RUN:
        queued = ExecutionRecord(
            proposal_id=proposal_id,
            approval_id=approval_id,
            command=command,
            cwd=cwd,
            status=ActionState.QUEUED.value,
            command_hash=current["command_hash"],
            risk_level=current["risk_level"],
            approved_by=approval.get("approved_by"),
            approval_scope=approval.get("approval_scope"),
            expires_at=approval.get("expires_at"),
            summary="Queued for execution mode check.",
        )
        ledger.append_transition(ActionState.APPROVED.value, queued)
        return ledger.append_transition(
            ActionState.QUEUED.value,
            ExecutionRecord(
                proposal_id=proposal_id,
                approval_id=approval_id,
                command=command,
                cwd=cwd,
                status=ActionState.BLOCKED.value,
                command_hash=current["command_hash"],
                risk_level=current["risk_level"],
                summary="Dry run mode: command was not executed.",
                verified_by_executor=True,
            ),
        )

    tokens = shlex.split(command)
    validate_command(command, tokens, confirmed=True)

    queued = ExecutionRecord(
        proposal_id=proposal_id,
        approval_id=approval_id,
        command=command,
        cwd=cwd,
        status=ActionState.QUEUED.value,
        command_hash=current["command_hash"],
        risk_level=current["risk_level"],
        approved_by=approval.get("approved_by"),
        approval_scope=approval.get("approval_scope"),
        expires_at=approval.get("expires_at"),
        summary="Queued for execution.",
    )
    ledger.transition(ActionState.APPROVED.value, queued.status)
    ledger.append(queued)

    try:
        sandbox = build_sandbox_invocation(tokens, cwd)
    except ToolError as exc:
        return ledger.append_transition(
            ActionState.QUEUED.value,
            ExecutionRecord(
                proposal_id=proposal_id,
                approval_id=approval_id,
                command=command,
                cwd=cwd,
                status=ActionState.BLOCKED.value,
                command_hash=current["command_hash"],
                risk_level=current["risk_level"],
                approved_by=approval.get("approved_by"),
                approval_scope=approval.get("approval_scope"),
                expires_at=approval.get("expires_at"),
                summary=str(exc),
                verified_by_executor=True,
            ),
        )
    exec_tokens = sandbox.tokens if sandbox.enabled else tokens
    exec_cwd = cwd if not sandbox.enabled else None
    execution_summary = (
        f"Process started in sandbox via {sandbox.engine} using {sandbox.image}."
        if sandbox.enabled
        else "Process started."
    )

    out_dir = artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = out_dir / f"{proposal_id}.stdout.log"
    stderr_path = out_dir / f"{proposal_id}.stderr.log"

    proc = await asyncio.create_subprocess_exec(
        *exec_tokens,
        cwd=exec_cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _RUNNING_PROCESSES[proposal_id] = proc
    running = ExecutionRecord(
        proposal_id=proposal_id,
        approval_id=approval_id,
        command=command,
        cwd=cwd,
        status=ActionState.RUNNING.value,
        pid=proc.pid,
        started_at=utc_now(),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        command_hash=current["command_hash"],
        risk_level=current["risk_level"],
        approved_by=approval.get("approved_by"),
        approval_scope=approval.get("approval_scope"),
        expires_at=approval.get("expires_at"),
        summary=execution_summary,
    )
    ledger.transition(ActionState.QUEUED.value, running.status)
    ledger.append(running)
    if on_event:
        await on_event(asdict(running))

    async def pump(stream, path: Path, stream_name: str) -> None:
        assert stream is not None
        with path.open("ab") as f:
            while True:
                chunk = await stream.readline()
                if not chunk:
                    break
                f.write(chunk)
                f.flush()
                if on_event:
                    await on_event(
                        {
                            "type": "EXECUTION_OUTPUT",
                            "proposal_id": proposal_id,
                            "approval_id": approval_id,
                            "stream": stream_name,
                            "chunk": chunk.decode("utf-8", errors="replace"),
                        }
                    )

    stdout_task = asyncio.create_task(pump(proc.stdout, stdout_path, "stdout"))
    stderr_task = asyncio.create_task(pump(proc.stderr, stderr_path, "stderr"))

    status = ActionState.FAILED
    summary = ""
    try:
        await asyncio.wait_for(proc.wait(), timeout=max(1, timeout_s))
        await stdout_task
        await stderr_task
        if proposal_id in _CANCEL_REQUESTS:
            status = ActionState.CANCELLED
        else:
            status = (
                ActionState.SUCCEEDED if proc.returncode == 0 else ActionState.FAILED
            )
        summary = (
            "Command completed with exit_code 0."
            if proc.returncode == 0
            else f"Command failed with exit_code {proc.returncode}."
        )
        if status == ActionState.CANCELLED:
            summary = "Command cancelled by user request."
    except asyncio.TimeoutError:
        _CANCEL_REQUESTS.add(proposal_id)
        proc.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        await stdout_task
        await stderr_task
        status = ActionState.CANCELLED
        summary = f"Command cancelled after timeout {timeout_s}s."
    finally:
        _RUNNING_PROCESSES.pop(proposal_id, None)
        _CANCEL_REQUESTS.discard(proposal_id)

    finished = ExecutionRecord(
        proposal_id=proposal_id,
        approval_id=approval_id,
        command=command,
        cwd=cwd,
        status=status.value,
        pid=proc.pid,
        started_at=running.started_at,
        finished_at=utc_now(),
        exit_code=proc.returncode,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        command_hash=current["command_hash"],
        risk_level=current["risk_level"],
        approved_by=approval.get("approved_by"),
        approval_scope=approval.get("approval_scope"),
        expires_at=approval.get("expires_at"),
        summary=summary,
        verified_by_executor=True,
    )
    ledger.transition(ActionState.RUNNING.value, finished.status)
    payload = ledger.append(finished)
    if on_event:
        await on_event(payload)
    return payload


async def cancel_execution(
    proposal_id: str,
    *,
    reason: str = "Cancelled by user.",
    ledger: ExecutionLedger | None = None,
) -> dict:
    ledger = ledger or ExecutionLedger()
    current = ledger.latest(proposal_id)
    if not current:
        raise ToolError("Proposal not found.")
    status = ActionState(current["status"])
    if status in TERMINAL_STATES:
        return current

    proc = _RUNNING_PROCESSES.get(proposal_id)
    if status == ActionState.RUNNING and proc:
        _CANCEL_REQUESTS.add(proposal_id)
        proc.send_signal(signal.SIGTERM)
        return dict(current, summary="Cancellation requested.")

    if status == ActionState.DRAFT:
        proposed = ExecutionRecord(
            proposal_id=proposal_id,
            approval_id=current.get("approval_id"),
            command=current["command"],
            cwd=current["cwd"],
            status=ActionState.PROPOSED.value,
            command_hash=current["command_hash"],
            risk_level=current.get("risk_level", "LOW"),
            summary="Draft promoted before cancellation.",
            verified_by_executor=False,
        )
        ledger.append_transition(ActionState.DRAFT.value, proposed)
        current = asdict(proposed)
        status = ActionState.PROPOSED

    if status not in {
        ActionState.PROPOSED,
        ActionState.APPROVED,
        ActionState.QUEUED,
        ActionState.RUNNING,
    }:
        raise ToolError(f"Cannot cancel execution in status {status.value}.")

    record = ExecutionRecord(
        proposal_id=proposal_id,
        approval_id=current.get("approval_id"),
        command=current["command"],
        cwd=current["cwd"],
        status=ActionState.CANCELLED.value,
        pid=current.get("pid"),
        started_at=current.get("started_at"),
        finished_at=utc_now(),
        exit_code=current.get("exit_code"),
        stdout_path=current.get("stdout_path"),
        stderr_path=current.get("stderr_path"),
        command_hash=current["command_hash"],
        risk_level=current.get("risk_level", "LOW"),
        approved_by=current.get("approved_by"),
        approval_scope=current.get("approval_scope"),
        expires_at=current.get("expires_at"),
        summary=reason,
        verified_by_executor=True,
    )
    return ledger.append_transition(status.value, record)


def assert_verified_completion(proposal_id: str) -> dict:
    result = read_execution_result(proposal_id)
    if (
        result.get("status") == ActionState.SUCCEEDED.value
        and result.get("exit_code") == 0
        and result.get("verified_by_executor") is True
    ):
        return result
    raise ToolError(
        "Ainda não executei. Preciso criar uma proposta de comando para aprovação."
    )


def guard_agent_claim(text: str, *, proposal_id: str | None = None) -> str:
    lowered = (text or "").lower()
    guarded_terms = [
        "estou fazendo",
        "vou executar",
        "corrigi",
        "apliquei",
        "feito",
        "concluído",
        "concluido",
    ]
    if not any(term in lowered for term in guarded_terms):
        return text
    if proposal_id:
        try:
            assert_verified_completion(proposal_id)
            return text
        except ToolError:
            pass
    return "Ainda não executei. Preciso criar uma proposta de comando para aprovação."
