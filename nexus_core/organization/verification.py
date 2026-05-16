from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from nexus_core.execution_protocol import ActionState
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.sentry_observability import capture_message


class VerificationEngine:
    """Evidence-first verification for runtime actions."""

    def __init__(self, memory: OrganizationalMemoryStore | None = None) -> None:
        self.memory = memory

    def verify_execution(
        self, result: dict[str, Any], *, command_id: str | None = None
    ) -> dict[str, Any]:
        evidence = {
            "proposal_id": result.get("proposal_id"),
            "approval_id": result.get("approval_id"),
            "exit_code": result.get("exit_code"),
            "status": result.get("status"),
            "verified_by_executor": result.get("verified_by_executor"),
            "stdout_path": result.get("stdout_path"),
            "stderr_path": result.get("stderr_path"),
            "stdout_exists": _path_exists(result.get("stdout_path")),
            "stderr_exists": _path_exists(result.get("stderr_path")),
            "stdout_tail": (result.get("stdout") or "")[-2000:],
            "stderr_tail": (result.get("stderr") or "")[-2000:],
        }
        ok = (
            result.get("status") == ActionState.SUCCEEDED.value
            and result.get("exit_code") == 0
            and result.get("verified_by_executor") is True
        )
        status = "passed" if ok else "failed"
        error = (
            ""
            if ok
            else result.get("summary") or "Execution did not pass verification."
        )
        recorded = self._record(
            target_type="execution",
            target=str(result.get("proposal_id") or "unknown"),
            status=status,
            command_id=command_id,
            evidence=evidence,
            error=error,
        )
        if status == "failed":
            capture_message(
                "Verification failed",
                module="verification",
                level="error",
                tags={
                    "command_id": command_id,
                    "execution_status": result.get("status"),
                },
                context=recorded,
            )
        return recorded

    def fingerprint_file(self, path: str | Path) -> dict[str, Any]:
        target = Path(path).expanduser()
        if not target.exists() or not target.is_file():
            return {"exists": target.exists(), "path": str(target), "sha256": None}
        h = hashlib.sha256()
        with target.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return {"exists": True, "path": str(target), "sha256": h.hexdigest()}

    def verify_file_changed(
        self,
        path: str | Path,
        *,
        before: dict[str, Any],
        command_id: str | None = None,
    ) -> dict[str, Any]:
        after = self.fingerprint_file(path)
        changed = before.get("sha256") != after.get("sha256") or before.get(
            "exists"
        ) != after.get("exists")
        return self._record(
            target_type="file",
            target=str(path),
            status="passed" if changed else "failed",
            command_id=command_id,
            evidence={"before": before, "after": after},
            error="" if changed else "File fingerprint did not change.",
        )

    def verify_process_started(
        self, pid: int | None, *, command_id: str | None = None
    ) -> dict[str, Any]:
        proc_path = Path("/proc") / str(pid) if pid else None
        ok = bool(proc_path and proc_path.exists())
        return self._record(
            target_type="process",
            target=str(pid or "unknown"),
            status="passed" if ok else "failed",
            command_id=command_id,
            evidence={"pid": pid, "proc_exists": ok},
            error="" if ok else "Process is not visible in /proc.",
        )

    def _record(
        self,
        *,
        target_type: str,
        target: str,
        status: str,
        command_id: str | None,
        evidence: dict[str, Any],
        error: str = "",
    ) -> dict[str, Any]:
        if self.memory:
            return self.memory.record_verification(
                target_type=target_type,
                target=target,
                status=status,
                command_id=command_id,
                evidence=evidence,
                error=error,
            )
        return {
            "target_type": target_type,
            "target": target,
            "status": status,
            "command_id": command_id,
            "evidence": evidence,
            "error": error,
        }


def _path_exists(path: str | None) -> bool:
    return bool(path and Path(path).exists())
