from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_project_env() -> bool:
    """Load the project .env once, without making imports depend on dotenv."""
    if os.getenv("ZEUS_SKIP_DOTENV", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    try:
        from dotenv import load_dotenv
    except Exception:
        return False

    project_root = Path(__file__).resolve().parents[1]
    return bool(load_dotenv(project_root / ".env"))


def env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}
