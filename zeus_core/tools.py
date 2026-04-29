import datetime
import os
import shlex
import subprocess
from pathlib import Path


class ToolError(Exception):
    pass


def _project_root() -> Path:
    env_root = os.getenv("ZEUS_PROJECT_ROOT", "").strip()
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

    root = _project_root()
    args = shlex.split(command)
    try:
        completed = subprocess.run(
            args,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as e:
        raise ToolError(f"Comando não encontrado: {args[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise ToolError(f"Timeout ao executar comando após {timeout_s}s.") from e

    return {
        "command": command,
        "cwd": str(root),
        "exit_code": completed.returncode,
        "stdout": (completed.stdout or "")[:50_000],
        "stderr": (completed.stderr or "")[:50_000],
    }


# Compat: algumas camadas podem importar execute_bash; o padrão Mark-like é cmd_control
def cmd_control(command: str, *, timeout_s: int = 30) -> dict:
    return execute_bash(command, timeout_s=timeout_s)
