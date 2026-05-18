from __future__ import annotations

from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.organization.workspace_context import WorkspaceMemory


def test_workspace_memory_detects_project_traits(tmp_path):
    (tmp_path / "nexus-iced").mkdir()
    (tmp_path / "nexus-iced" / "Cargo.toml").write_text(
        '[package]\nname = "nexus-iced"\n[dependencies]\niced = "0.12"\n',
        encoding="utf-8",
    )
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "Cargo.toml").write_text(
        '[package]\nname = "backend"\n[dependencies]\naxum = "0.7"\nsqlx = "0.7"\n',
        encoding="utf-8",
    )
    (tmp_path / "nexus_core").mkdir()
    (tmp_path / "nexus_core" / "execution_protocol.py").write_text(
        "# evidence first\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    store = OrganizationalMemoryStore(tmp_path / "memory.sqlite3")
    blackboard = Blackboard(tmp_path / "blackboard.json", memory=store)

    context = WorkspaceMemory(tmp_path).analyze()
    WorkspaceMemory(tmp_path).persist(context, blackboard=blackboard, memory=store)

    tags = set(context["tags"])
    assert "rust_project" in tags
    assert "iced_frontend" in tags
    assert "axum_backend" in tags
    assert "uses_sqlx" in tags
    assert "python_runtime" in tags
    assert blackboard.get("workspace_context")["tags"] == context["tags"]
    assert store.list_memory_entries(scope="workspace")[0]["kind"] == "context"
