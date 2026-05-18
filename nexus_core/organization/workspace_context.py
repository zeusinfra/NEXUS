from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nexus_core.organization.blackboard import Blackboard, utc_now
from nexus_core.organization.memory import OrganizationalMemoryStore


SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
}


class WorkspaceMemory:
    """Detects stable project facts and stores them as workspace context."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def analyze(self) -> dict[str, Any]:
        cargo_files = self._find_named("Cargo.toml", max_depth=4, limit=40)
        package_files = self._find_named("package.json", max_depth=3, limit=20)
        python_markers = [
            path
            for path in (
                self.project_root / "pyproject.toml",
                self.project_root / "nexus_core",
                self.project_root / "tests",
            )
            if path.exists()
        ]
        source_paths = self._source_paths(max_depth=4, limit=260)
        cargo_text = "\n".join(_read_text(path) for path in cargo_files).lower()
        path_text = "\n".join(
            str(path.relative_to(self.project_root)) for path in source_paths
        )
        path_text_lower = path_text.lower()

        tags: list[str] = []
        components: list[dict[str, Any]] = []
        languages: list[str] = []

        if cargo_files:
            tags.append("rust_project")
            languages.append("rust")
            components.append(_component("rust", cargo_files))
        if "iced" in cargo_text or (self.project_root / "nexus-iced").exists():
            tags.append("iced_frontend")
            components.append(
                _component("iced_frontend", [self.project_root / "nexus-iced"])
            )
        if "axum" in cargo_text:
            tags.append("axum_backend")
        if "sqlx" in cargo_text:
            tags.append("uses_sqlx")
        if "websocket" in cargo_text or "websocket" in path_text_lower:
            tags.append("websocket_architecture")
        if python_markers:
            tags.append("python_runtime")
            languages.append("python")
            components.append(_component("python_core", python_markers))
        if package_files:
            tags.append("node_project")
            languages.append("javascript")
            components.append(_component("node", package_files))
        if (self.project_root / "tests").exists():
            tags.append("has_test_suite")
        if (self.project_root / "nexus_core" / "organization").exists():
            tags.append("organization_runtime")
        if (self.project_root / "nexus_core" / "execution_protocol.py").exists():
            tags.append("evidence_first_execution")

        tags = _dedupe(tags)
        context = {
            "root": str(self.project_root),
            "tags": tags,
            "languages": _dedupe(languages),
            "components": components,
            "evidence": {
                "cargo_files": _relative_list(self.project_root, cargo_files),
                "package_files": _relative_list(self.project_root, package_files),
                "python_markers": _relative_list(self.project_root, python_markers),
            },
            "updated_at": utc_now(),
        }
        return context

    def persist(
        self,
        context: dict[str, Any],
        *,
        blackboard: Blackboard,
        memory: OrganizationalMemoryStore,
        record_entry: bool = True,
    ) -> dict[str, Any]:
        blackboard.set_workspace_context(context)
        if record_entry:
            memory.record_memory_entry(
                scope="workspace",
                kind="context",
                content=", ".join(context.get("tags") or []) or "workspace detected",
                source="workspace_context",
                metadata=context,
            )
            blackboard.append_event(
                "ORG_WORKSPACE_CONTEXT_REFRESHED",
                {
                    "tags": context.get("tags", []),
                    "languages": context.get("languages", []),
                },
            )
        return context

    def _find_named(
        self, filename: str, *, max_depth: int, limit: int
    ) -> list[Path]:
        matches: list[Path] = []
        for path in self._walk(max_depth=max_depth):
            if path.name == filename:
                matches.append(path)
                if len(matches) >= limit:
                    break
        return matches

    def _source_paths(self, *, max_depth: int, limit: int) -> list[Path]:
        paths: list[Path] = []
        for path in self._walk(max_depth=max_depth):
            if path.suffix in {
                ".py",
                ".rs",
                ".toml",
                ".json",
                ".ts",
                ".tsx",
                ".js",
            }:
                paths.append(path)
                if len(paths) >= limit:
                    break
        return paths

    def _walk(self, *, max_depth: int) -> list[Path]:
        root = self.project_root
        if not root.exists():
            return []
        output: list[Path] = []
        for current, dirs, files in os.walk(root):
            current_path = Path(current)
            try:
                depth = len(current_path.relative_to(root).parts)
            except ValueError:
                continue
            dirs[:] = [
                item
                for item in dirs
                if item not in SKIP_DIRS and not item.startswith(".")
            ]
            if depth >= max_depth:
                dirs[:] = []
            for filename in files:
                output.append(current_path / filename)
        return output


def _read_text(path: Path, *, limit: int = 80_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _component(name: str, paths: list[Path]) -> dict[str, Any]:
    return {
        "name": name,
        "paths": [str(path) for path in paths[:6]],
    }


def _relative_list(root: Path, paths: list[Path]) -> list[str]:
    values = []
    for path in paths:
        try:
            values.append(str(path.relative_to(root)))
        except ValueError:
            values.append(str(path))
    return values


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def context_to_json(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True)
