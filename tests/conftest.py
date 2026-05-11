from __future__ import annotations

import os
from pathlib import Path

import pytest


os.environ.setdefault("NEXUS_TESTING", "1")
os.environ.setdefault("NEXUS_SKIP_DOTENV", "1")
os.environ["NEXUS_AUTONOMY_LEVEL"] = "GUARDED"
os.environ.setdefault("NEXUS_ENABLE_VOICE", "0")
os.environ.setdefault("NEXUS_ENABLE_VOICE_SENSING", "0")
os.environ.setdefault("NEXUS_ENABLE_BROWSER_SENSING", "0")
os.environ.setdefault("NEXUS_ENABLE_INTERNAL_WATCHER", "0")
os.environ.setdefault("NEXUS_ENABLE_SECOND_BRAIN", "0")
os.environ.setdefault("NEXUS_COGNITIVE_LOOP_ENABLED", "0")
os.environ.setdefault("NEXUS_ENABLE_AUTONOMOUS_TASKS", "0")


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Keep tests away from developer runtime state by default."""
    db_path = tmp_path / "nexus_test.db"
    data_dir = tmp_path / "data"
    vault_dir = tmp_path / "vault"
    data_dir.mkdir()
    vault_dir.mkdir()

    monkeypatch.setenv("NEXUS_TESTING", "1")
    monkeypatch.setenv("NEXUS_DB_PATH", str(db_path))
    monkeypatch.setenv("NEXUS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("NEXUS_VAULT_PATH", str(vault_dir))
    monkeypatch.setenv("NEXUS_AUTONOMY_LEVEL", "GUARDED")
    monkeypatch.setenv("NEXUS_ENABLE_VOICE", "0")
    monkeypatch.setenv("NEXUS_ENABLE_VOICE_SENSING", "0")
    monkeypatch.setenv("NEXUS_ENABLE_BROWSER_SENSING", "0")
    monkeypatch.setenv("NEXUS_ENABLE_INTERNAL_WATCHER", "0")
    monkeypatch.setenv("NEXUS_ENABLE_SECOND_BRAIN", "0")
    monkeypatch.setenv("NEXUS_COGNITIVE_LOOP_ENABLED", "0")
    monkeypatch.setenv("NEXUS_ENABLE_AUTONOMOUS_TASKS", "0")

    yield
