from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None


def project_root() -> Path:
    env_root = os.getenv("NEXUS_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class NexusOrgConfig:
    project_root: Path
    runtime_dir: Path
    state_dir: Path
    logs_dir: Path
    tasks_dir: Path
    approvals_dir: Path
    pid_dir: Path
    blackboard_path: Path
    daemon_status_path: Path
    daemon_pid_path: Path
    memory_db_path: Path
    summaries_dir: Path
    decisions_dir: Path
    heartbeat_interval_s: float = 5.0
    cognitive_tick_s: float = 15.0
    autonomy_level: str = "GUARDED"
    dry_run_default: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None = None) -> "NexusOrgConfig":
        data = data or {}
        root = (
            Path(
                os.getenv("NEXUS_PROJECT_ROOT")
                or data.get("project_root")
                or project_root()
            )
            .expanduser()
            .resolve()
        )

        runtime_cfg = (
            data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
        )
        daemon_cfg = (
            data.get("daemon", {}) if isinstance(data.get("daemon"), dict) else {}
        )
        policy_cfg = (
            data.get("policy", {}) if isinstance(data.get("policy"), dict) else {}
        )
        memory_cfg = (
            data.get("memory", {}) if isinstance(data.get("memory"), dict) else {}
        )

        runtime_dir = _path_from(
            root, os.getenv("NEXUS_RUNTIME_DIR") or runtime_cfg.get("dir") or "runtime"
        )
        state_dir = _path_from(
            root, runtime_cfg.get("state_dir") or runtime_dir / "state"
        )
        logs_dir = _path_from(
            root, os.getenv("NEXUS_LOG_DIR") or runtime_cfg.get("logs_dir") or "logs"
        )
        tasks_dir = _path_from(
            root, runtime_cfg.get("tasks_dir") or runtime_dir / "tasks"
        )
        approvals_dir = _path_from(
            root, runtime_cfg.get("approvals_dir") or runtime_dir / "approvals"
        )
        pid_dir = _path_from(root, runtime_cfg.get("pid_dir") or runtime_dir / "pids")
        blackboard_path = _path_from(
            root,
            runtime_cfg.get("blackboard_path") or state_dir / "blackboard.json",
        )
        daemon_status_path = _path_from(
            root,
            runtime_cfg.get("daemon_status_path") or state_dir / "daemon_status.json",
        )
        daemon_pid_path = _path_from(
            root,
            runtime_cfg.get("daemon_pid_path") or pid_dir / "organization.pid",
        )
        memory_db_path = _path_from(
            root,
            os.getenv("NEXUS_ORG_MEMORY_DB")
            or memory_cfg.get("sqlite_path")
            or "memory/organizational_memory.sqlite3",
        )
        summaries_dir = _path_from(
            root, memory_cfg.get("summaries_dir") or "memory/summaries"
        )
        decisions_dir = _path_from(
            root, memory_cfg.get("decisions_dir") or "memory/decisions"
        )

        return cls(
            project_root=root,
            runtime_dir=runtime_dir,
            state_dir=state_dir,
            logs_dir=logs_dir,
            tasks_dir=tasks_dir,
            approvals_dir=approvals_dir,
            pid_dir=pid_dir,
            blackboard_path=blackboard_path,
            daemon_status_path=daemon_status_path,
            daemon_pid_path=daemon_pid_path,
            memory_db_path=memory_db_path,
            summaries_dir=summaries_dir,
            decisions_dir=decisions_dir,
            heartbeat_interval_s=float(daemon_cfg.get("heartbeat_interval_s", 5.0)),
            cognitive_tick_s=float(daemon_cfg.get("cognitive_tick_s", 15.0)),
            autonomy_level=str(policy_cfg.get("autonomy_level", "GUARDED")).upper(),
            dry_run_default=bool(policy_cfg.get("dry_run_default", True)),
        )

    def ensure_directories(self) -> None:
        for path in (
            self.runtime_dir,
            self.state_dir,
            self.logs_dir,
            self.tasks_dir,
            self.approvals_dir,
            self.pid_dir,
            self.memory_db_path.parent,
            self.summaries_dir,
            self.decisions_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def load_org_config(path: str | Path | None = None) -> NexusOrgConfig:
    config_path = Path(
        path
        or os.getenv("NEXUS_CONFIG_PATH", "").strip()
        or project_root() / "configs" / "nexus.toml"
    ).expanduser()
    data: dict[str, Any] = {}
    if config_path.exists():
        if tomllib is None:
            raise RuntimeError(
                "tomllib is required to read nexus.toml on this Python version."
            )
        with config_path.open("rb") as f:
            data = tomllib.load(f)
    return NexusOrgConfig.from_mapping(data)


def _path_from(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()
