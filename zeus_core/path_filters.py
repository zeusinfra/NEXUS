import os
from pathlib import Path


IGNORED_RUNTIME_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    "logs",
    "data",
    "scratch",
    ".obsidian",
    ".pytest_cache",
    ".ruff_cache",
    "proc",
    "sys",
    "dev",
    "run",
    "tmp",
    "mnt",
    "media",
    "lost+found",
}

IGNORED_RUNTIME_EXTENSIONS = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-journal",
    ".db-wal",
    ".db-shm",
    ".log",
    ".tmp",
    ".pyc",
    ".lock",
    ".pid",
    ".onnx",
    ".mp3",
}

IGNORED_RUNTIME_FILES = {
    "zeus_events.db",
    "zeus_events.db-journal",
    "zeus_events.db-wal",
    "zeus_events.db-shm",
    "zeus_core.log",
    "zeus_server.log",
}


def is_runtime_noise_path(path: str | os.PathLike) -> bool:
    candidate = Path(path)
    parts = set(candidate.parts)
    if any(part.startswith(".") for part in candidate.parts):
        return True
    if parts & IGNORED_RUNTIME_DIRS:
        return True
    name = candidate.name
    if name in IGNORED_RUNTIME_FILES:
        return True
    lowered = name.lower()
    return any(lowered.endswith(ext) for ext in IGNORED_RUNTIME_EXTENSIONS)
