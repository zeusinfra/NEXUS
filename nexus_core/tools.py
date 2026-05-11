import datetime
import os
import asyncio
from pathlib import Path


class ToolError(Exception):
    pass


def _project_root() -> Path:
    env_root = os.getenv("NEXUS_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _resolve_project_path(path: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ToolError("Caminho inválido.")

    root = _project_root()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()

    try:
        candidate.relative_to(root)
    except Exception as e:
        raise ToolError(f"Acesso negado fora do projeto: {candidate}") from e

    return candidate


def get_time() -> dict:
    now = datetime.datetime.now().astimezone()
    return {"iso": now.isoformat(timespec="seconds")}


def read_file(path: str, max_bytes: int = 200_000) -> dict:
    target = _resolve_project_path(path)
    if not target.exists():
        raise ToolError(f"Arquivo não encontrado: {target}")
    if not target.is_file():
        raise ToolError(f"Não é um arquivo: {target}")

    data = target.read_bytes()
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True

    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        content = data.decode("utf-8", errors="replace")

    return {
        "path": str(target),
        "content": content,
        "truncated": truncated,
        "bytes": len(data),
    }


def write_file(path: str, content: str, *, mode: str = "overwrite") -> dict:
    if not isinstance(content, str):
        raise ToolError("Conteúdo inválido (esperado string).")

    target = _resolve_project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if mode not in {"overwrite", "append"}:
        raise ToolError("Modo inválido. Use 'overwrite' ou 'append'.")

    open_mode = "w" if mode == "overwrite" else "a"
    with open(target, open_mode, encoding="utf-8") as f:
        f.write(content)

    return {"path": str(target), "bytes_written": len(content.encode("utf-8"))}


def execute_bash(command: str, *, timeout_s: int = 30) -> dict:
    if not isinstance(command, str) or not command.strip():
        raise ToolError("Comando inválido.")

    from nexus_core.execution_protocol import create_command_proposal

    proposal = create_command_proposal(command, cwd=str(_project_root()))
    return {
        "command": command,
        "requires_approval": proposal["status"] == "PROPOSED",
        "proposal_id": proposal["proposal_id"],
        "status": proposal["status"],
        "cwd": proposal["cwd"],
        "risk_level": proposal["risk_level"],
        "message": (
            "Ainda não executei. Preciso de aprovação para executar este comando."
            if proposal["status"] == "PROPOSED"
            else proposal["summary"]
        ),
    }


# Compat: algumas camadas podem importar execute_bash; o padrão Mark-like é cmd_control
def cmd_control(
    command: str,
    *,
    timeout_s: int = 30,
    proposal_id: str | None = None,
    approval_id: str | None = None,
) -> dict:
    if not isinstance(command, str) or not command.strip():
        raise ToolError("Comando inválido.")

    from nexus_core.execution_protocol import (
        create_command_proposal,
        execute_approved_command,
        read_execution_result,
    )

    if not approval_id:
        proposal = create_command_proposal(command, cwd=str(_project_root()))
        return {
            "command": command,
            "requires_approval": proposal["status"] == "PROPOSED",
            "proposal_id": proposal["proposal_id"],
            "status": proposal["status"],
            "cwd": proposal["cwd"],
            "risk_level": proposal["risk_level"],
            "message": (
                "Ainda não executei. Preciso de aprovação para executar este comando."
                if proposal["status"] == "PROPOSED"
                else proposal["summary"]
            ),
        }
    if not proposal_id:
        raise ToolError("cmd_control requer proposal_id junto com approval_id.")
    execution = asyncio.run(
        execute_approved_command(proposal_id, approval_id, timeout_s=timeout_s)
    )
    result = read_execution_result(proposal_id)
    return {
        "command": command,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": execution.get("status"),
        "pid": execution.get("pid"),
        "exit_code": execution.get("exit_code"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "stdout_path": execution.get("stdout_path"),
        "stderr_path": execution.get("stderr_path"),
        "verified_by_executor": execution.get("verified_by_executor"),
    }
