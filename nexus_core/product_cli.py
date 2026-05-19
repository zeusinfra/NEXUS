from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from nexus_core.health_status import build_external_watcher_status, check_memory_service
from nexus_core.model_router import ModelRouter
from nexus_core.models.model_registry import model_status
from nexus_core.models.ollama_client import OllamaClient


RUNTIME_COMPAT_BLOCK = """

# Added by nexus setup for the system daemon.
project_root = "/usr/lib/nexus"

[runtime]
dir = "/var/lib/nexus"
state_dir = "/var/lib/nexus/state"
logs_dir = "/var/log/nexus"
tasks_dir = "/var/lib/nexus/tasks"
approvals_dir = "/var/lib/nexus/approvals"
pid_dir = "/var/lib/nexus/pids"
blackboard_path = "/var/lib/nexus/state/blackboard.json"
daemon_status_path = "/var/lib/nexus/state/daemon_status.json"
daemon_pid_path = "/var/lib/nexus/pids/organization.pid"

[daemon]
heartbeat_interval_s = 5.0
cognitive_tick_s = 15.0

[policy]
autonomy_level = "GUARDED"
dry_run_default = true

[memory]
sqlite_path = "/var/lib/nexus/memory/organizational_memory.sqlite3"
summaries_dir = "/var/lib/nexus/memory/summaries"
decisions_dir = "/var/lib/nexus/memory/decisions"
"""


@dataclass(frozen=True)
class ProductPaths:
    project_root: Path
    state_dir: Path
    logs_dir: Path
    status_path: Path
    pid_path: Path
    config_path: Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexus")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup")
    setup.add_argument(
        "--apply",
        action="store_true",
        help="write system config when not running as root",
    )
    sub.add_parser("status")
    sub.add_parser("health")
    sub.add_parser("doctor")
    sub.add_parser("config")
    sub.add_parser("uninstall")

    logs = sub.add_parser("logs")
    logs.add_argument("--follow", action="store_true")
    logs.add_argument("--lines", type=int, default=80)

    model = sub.add_parser("model")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    model_sub.add_parser("status")
    model_sub.add_parser("list-local")
    model_sub.add_parser("test-local")
    model_sub.add_parser("test-cloud")
    set_local = model_sub.add_parser("set-local")
    set_local.add_argument("model")
    set_cloud = model_sub.add_parser("set-cloud")
    set_cloud.add_argument("model")

    router = sub.add_parser("router")
    router_sub = router.add_subparsers(dest="router_command", required=True)
    explain = router_sub.add_parser("explain")
    explain.add_argument("task", nargs="+")

    ask = sub.add_parser("ask")
    ask.add_argument("question", nargs="+")
    run = sub.add_parser("run")
    run.add_argument("task", nargs="+")

    agents = sub.add_parser("agents")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)
    agents_sub.add_parser("status")
    restart = agents_sub.add_parser("restart")
    restart.add_argument("agent")

    args = parser.parse_args(argv)
    if args.command == "setup":
        return _print(setup_payload(apply=args.apply or os.geteuid() == 0))
    if args.command == "status":
        return _print(status_payload())
    if args.command in {"health", "doctor"}:
        return _print(health_payload())
    if args.command == "config":
        return _print(config_payload())
    if args.command == "uninstall":
        return _print(uninstall_payload())
    if args.command == "logs":
        return _logs(follow=args.follow, lines=args.lines)
    if args.command == "model":
        return _model(args)
    if args.command == "router":
        return _print(ModelRouter().classify(" ".join(args.task)).to_dict())
    if args.command == "ask":
        return _ask(" ".join(args.question))
    if args.command == "run":
        return _print(
            {
                "ok": False,
                "message": "Use 'nexus org propose-command' para execução real com aprovação. O roteamento abaixo não executou nada.",
                "routing": ModelRouter().classify(" ".join(args.task)).to_dict(),
            }
        )
    if args.command == "agents":
        return _agents(args)
    raise SystemExit(f"unknown command: {args.command}")


def setup_payload(*, apply: bool) -> dict[str, Any]:
    targets = {
        "config_dir": Path("/etc/nexus"),
        "data_dir": Path("/var/lib/nexus"),
        "workspace_dir": Path("/var/lib/nexus/workspace"),
        "log_dir": Path("/var/log/nexus"),
        "config": Path("/etc/nexus/config.toml"),
        "env": Path("/etc/nexus/nexus.env"),
    }
    project_root = Path(__file__).resolve().parents[1]
    example_config = project_root / "config" / "config.example.toml"
    example_env = project_root / "config" / "nexus.env.example"

    if not apply:
        return {
            "ok": False,
            "message": "Rode com sudo ou use --apply para gravar a configuração do sistema.",
            "would_create": {key: str(value) for key, value in targets.items()},
        }

    created: list[str] = []
    for key in ("config_dir", "data_dir", "workspace_dir", "log_dir"):
        targets[key].mkdir(parents=True, exist_ok=True)
        created.append(str(targets[key]))

    if not targets["config"].exists():
        shutil.copyfile(example_config, targets["config"])
        created.append(str(targets["config"]))
    else:
        current_config = targets["config"].read_text(encoding="utf-8")
        if "[runtime]" not in current_config:
            targets["config"].write_text(
                current_config.rstrip() + RUNTIME_COMPAT_BLOCK,
                encoding="utf-8",
            )
            created.append(f"{targets['config']} (migrated)")
    if not targets["env"].exists():
        shutil.copyfile(example_env, targets["env"])
        created.append(str(targets["env"]))

    state_dir = targets["data_dir"] / "state"
    pid_dir = targets["data_dir"] / "pids"
    state_dir.mkdir(parents=True, exist_ok=True)
    pid_dir.mkdir(parents=True, exist_ok=True)
    created.extend([str(state_dir), str(pid_dir)])

    return {
        "ok": True,
        "message": "Configuração base do NEXUS preparada. Edite /etc/nexus/nexus.env para adicionar secrets.",
        "created_or_verified": created,
        "next": [
            "nexus health",
            "systemctl enable --now nexus",
        ],
    }


def status_payload() -> dict[str, Any]:
    paths = product_paths()
    health = daemon_health(paths)
    models = model_status()
    return {
        "daemon": health,
        "models": models,
        "paths": {
            "project_root": str(paths.project_root),
            "data_dir": str(paths.state_dir),
            "log_dir": str(paths.logs_dir),
            "config": str(paths.config_path),
        },
        "autonomy_level": os.getenv("NEXUS_AUTONOMY_LEVEL", "GUARDED"),
    }


def config_payload() -> dict[str, Any]:
    return {
        "system_config": "/etc/nexus/config.toml",
        "system_env": "/etc/nexus/nexus.env",
        "example_config": str(
            Path(__file__).resolve().parents[1] / "config" / "config.example.toml"
        ),
        "example_env": str(
            Path(__file__).resolve().parents[1] / "config" / "nexus.env.example"
        ),
    }


def _backend_health() -> dict[str, Any]:
    url = f"http://127.0.0.1:{os.getenv('NEXUS_PORT', '8080')}/api/health"
    try:
        resp = requests.get(url, timeout=0.8)
        return {
            "status": "online" if resp.status_code == 200 else "offline",
            "url": url,
            "http_status": resp.status_code,
        }
    except Exception as exc:
        return {"status": "offline", "url": url, "error": str(exc)}


def _root_daemon_health() -> dict[str, Any]:
    socket_path = os.getenv("NEXUS_DAEMON_SOCKET", "/tmp/nexus/daemon.sock")
    enabled_env = os.getenv("NEXUS_ROOT_DAEMON_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    socket_exists = Path(socket_path).exists()
    return {
        "enabled_env": enabled_env,
        "enabled": enabled_env or socket_exists,
        "socket": socket_path,
        "socket_exists": socket_exists,
        "status": "online" if socket_exists else "offline",
        "detail": (
            "Root daemon socket detectado mesmo com NEXUS_ROOT_DAEMON_ENABLED desativado."
            if socket_exists and not enabled_env
            else "Root daemon habilitado via ambiente." if enabled_env else "Root daemon desativado."
        ),
    }


def health_payload() -> dict[str, Any]:
    status = status_payload()
    local = status["models"]["local"]
    cloud = status["models"]["cloud"]
    backend = _backend_health()
    memory = check_memory_service()
    watcher = build_external_watcher_status(status["paths"]["project_root"])
    root_daemon = _root_daemon_health()
    llm_ok = bool(local["api_ok"] or cloud["ready"])
    ffmpeg_available = bool(shutil.which("ffmpeg"))
    faster_whisper_available = importlib.util.find_spec("faster_whisper") is not None
    asr_ok = ffmpeg_available and faster_whisper_available
    ocr_ok = bool(shutil.which("tesseract"))

    checks = [
        {"name": "backend", "ok": backend["status"] == "online", "detail": backend.get("url")},
        {
            "name": "org_daemon",
            "ok": status["daemon"]["status"] in {"online", "stopped"},
            "detail": status["daemon"].get("detail"),
        },
        {
            "name": "root_daemon",
            "ok": root_daemon["status"] == "online",
            "detail": root_daemon.get("detail"),
        },
        {
            "name": "watcher",
            "ok": watcher["status"] == "online",
            "detail": f"port={watcher.get('port')} open={watcher.get('port_open')}",
        },
        {
            "name": "memory_service",
            "ok": memory["status"] == "online",
            "detail": (
                f"{memory.get('url')}"
                + (" (fallback_active)" if memory.get("fallback_active") else "")
            ),
        },
        {
            "name": "llm",
            "ok": llm_ok,
            "detail": local.get("selected_model")
            or cloud.get("model")
            or local.get("suggestion"),
        },
        {
            "name": "asr",
            "ok": asr_ok,
            "detail": (
                "ffmpeg + faster_whisper disponíveis"
                if asr_ok
                else "ffmpeg e/ou faster_whisper ausentes"
            ),
        },
        {
            "name": "ocr",
            "ok": ocr_ok,
            "detail": "tesseract disponível" if ocr_ok else "tesseract ausente",
        },
        {
            "name": "cloud_key",
            "ok": cloud["api_key_present"],
            "detail": cloud["api_key_env"],
        },
    ]

    return {
        "ok": all(check["ok"] for check in checks if check["name"] != "cloud_key"),
        "checks": checks,
        "backend": backend,
        "daemon": status["daemon"],
        "root_daemon": root_daemon,
        "watcher": watcher,
        "memory_service": memory,
        "llm": {"local": local, "cloud": cloud, "ok": llm_ok},
        "asr": {
            "ok": asr_ok,
            "ffmpeg_available": ffmpeg_available,
            "faster_whisper_available": faster_whisper_available,
        },
        "ocr": {"ok": ocr_ok, "tesseract_available": ocr_ok},
        **status,
    }


def product_paths() -> ProductPaths:
    explicit_dev = os.getenv("NEXUS_DEV_MODE") == "1"
    explicit_project_root = os.getenv("NEXUS_PROJECT_ROOT")
    package_installed = (
        Path("/usr/bin/nexus").exists() and Path("/etc/nexus/config.toml").exists()
    )
    use_system = package_installed and not explicit_dev and not explicit_project_root
    project_root = Path(
        explicit_project_root
        or ("/usr/lib/nexus" if use_system else Path(__file__).resolve().parents[1])
    ).resolve()
    installed = use_system or project_root == Path("/usr/lib/nexus")
    config_path = Path(
        os.getenv("NEXUS_CONFIG_PATH")
        or (
            "/etc/nexus/config.toml"
            if installed
            else project_root / "configs" / "nexus.toml"
        )
    ).resolve()
    state_dir = Path(
        os.getenv("NEXUS_STATE_DIR")
        or ("/var/lib/nexus/state" if installed else project_root / "runtime" / "state")
    ).resolve()
    runtime_dir = Path(
        os.getenv("NEXUS_RUNTIME_DIR")
        or ("/var/lib/nexus" if installed else project_root / "runtime")
    ).resolve()
    logs_dir = Path(
        os.getenv("NEXUS_LOG_DIR")
        or ("/var/log/nexus" if installed else project_root / "logs")
    ).resolve()
    return ProductPaths(
        project_root=project_root,
        state_dir=state_dir,
        logs_dir=logs_dir,
        status_path=state_dir / "daemon_status.json",
        pid_path=runtime_dir / "pids" / "organization.pid",
        config_path=config_path,
    )


def daemon_health(paths: ProductPaths) -> dict[str, Any]:
    status = _read_json(paths.status_path)
    pid = _read_pid(paths.pid_path)
    alive = _pid_alive(pid)
    heartbeat = status.get("last_heartbeat") if status else None
    age = _heartbeat_age(heartbeat)
    stale = age is None or age > 15.0 or not alive

    status_value = str(status.get("status") or "").lower()
    if not status:
        overall = "unknown"
        detail = "No daemon status file found."
    elif status_value == "stopped" and not alive:
        overall = "stopped"
        stale = False
        detail = "Daemon stopped cleanly and no PID is active."
    elif stale:
        overall = "stale"
        detail = "Daemon heartbeat is stale or PID is not alive."
    else:
        overall = "online"
        detail = "Daemon heartbeat and PID are healthy."

    return {
        "status": overall,
        "pid": pid,
        "pid_alive": alive,
        "heartbeat_age_s": round(age, 3) if age is not None else None,
        "stale": stale,
        "mode": str(status.get("mode") or "UNKNOWN"),
        "agents": int(status.get("agents") or 0),
        "tasks": int(status.get("tasks") or 0),
        "status_path": str(paths.status_path),
        "pid_path": str(paths.pid_path),
        "detail": detail,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def _pid_alive(pid: int | None) -> bool:
    return bool(pid and (Path("/proc") / str(pid)).exists())


def _heartbeat_age(value: object) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()


def _model(args: argparse.Namespace) -> int:
    client = OllamaClient()
    if args.model_command == "status":
        return _print(model_status())
    if args.model_command == "list-local":
        status = client.status()
        return _print(
            {
                "ready": status.ready,
                "selected_model": status.selected_model,
                "models": [model.__dict__ for model in status.models],
                "suggestion": None
                if status.selected_model
                else "Nenhum modelo local encontrado no Ollama. Rode, por exemplo: ollama pull qwen2.5:3b",
            }
        )
    if args.model_command == "test-local":
        response = client.generate("Responda apenas: NEXUS_LOCAL_OK")
        return _print(response.__dict__)
    if args.model_command == "test-cloud":
        cloud = model_status()["cloud"]
        return _print(
            {
                "ok": cloud["ready"],
                "provider": cloud["provider"],
                "model": cloud["model"],
                "message": "Cloud configurada."
                if cloud["ready"]
                else f"Defina {cloud['api_key_env']} ou OPENAI_API_KEY.",
            }
        )
    if args.model_command == "set-local":
        return _print(_env_assignment("NEXUS_LOCAL_MODEL", args.model))
    if args.model_command == "set-cloud":
        return _print(_env_assignment("NEXUS_CLOUD_MODEL", args.model))
    raise SystemExit(f"unknown model command: {args.model_command}")


def _agents(args: argparse.Namespace) -> int:
    if args.agents_command == "status":
        daemon = status_payload()["daemon"]
        return _print(
            {
                "ok": True,
                "daemon_status": daemon["status"],
                "agents_registered": daemon.get("agents", 0),
                "detail": daemon.get("detail"),
            }
        )
    if args.agents_command == "restart":
        return _print(
            {
                "ok": False,
                "message": "Reinicio individual ainda deve passar pelo daemon organizacional.",
                "agent": args.agent,
                "safe_command": f"nexus org health",
            }
        )
    raise SystemExit(f"unknown agents command: {args.agents_command}")


def _ask(question: str) -> int:
    decision = ModelRouter().classify(question)
    if decision.route == "local":
        response = OllamaClient().generate(question)
        return _print({"routing": decision.to_dict(), "response": response.__dict__})
    return _print(
        {
            "routing": decision.to_dict(),
            "ok": False,
            "message": "Tarefa roteada para cloud. Configure o provider e use o backend conversacional para execução estratégica.",
        }
    )


def _logs(*, follow: bool, lines: int) -> int:
    candidates = [
        Path("/var/log/nexus/nexus.log"),
        Path("/var/log/nexus/executor.log"),
        Path.cwd() / "nexus_server.log",
        Path.cwd() / "logs" / "nexus_organization_systemd.log",
    ]
    existing = next((path for path in candidates if path.exists()), None)
    if not existing:
        print("Nenhum log encontrado em /var/log/nexus ou no workspace atual.")
        return 1
    if follow:
        return subprocess.call(["tail", "-f", str(existing)])
    return subprocess.call(["tail", "-n", str(lines), str(existing)])


def _env_assignment(key: str, value: str) -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Persistencia segura deve ser feita em /etc/nexus/nexus.env pelo setup.",
        "export": f"export {key}={value}",
    }


def uninstall_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Para remover o pacote sem apagar dados: sudo apt remove nexus",
        "preserved_data": ["/var/lib/nexus", "/var/log/nexus", "/etc/nexus"],
        "purge_note": "Remova dados manualmente apenas se tiver backup e certeza operacional.",
    }


def _print(payload: object) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
