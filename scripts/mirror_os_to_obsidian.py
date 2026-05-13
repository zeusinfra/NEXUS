#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EXCLUDE_PREFIXES = {
    "/dev",
    "/proc",
    "/run",
    "/sys",
    "/tmp",
    "/var/tmp",
}

DEFAULT_STUB_PREFIXES = {
    "/boot",
    "/dev",
    "/proc",
    "/run",
    "/sys",
    "/tmp",
    "/var/cache",
    "/var/lib/docker",
    "/var/lib/flatpak",
    "/var/log",
    "/var/tmp",
}


@dataclass
class MirrorStats:
    notes_written: int = 0
    dirs_seen: int = 0
    files_seen: int = 0
    symlinks_seen: int = 0
    skipped: int = 0
    permission_denied: int = 0
    errors: list[str] = field(default_factory=list)
    stubbed: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser().resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
    except OSError:
        return False


def _as_posix(path: Path) -> str:
    value = str(path)
    if value != "/" and value.endswith("/"):
        return value.rstrip("/")
    return value


def _matches_prefix(path: Path, prefixes: set[str]) -> bool:
    value = _as_posix(path)
    for prefix in prefixes:
        if value == prefix or value.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


def _safe_component(value: str) -> str:
    if not value:
        return "ROOT"
    safe = value.replace("/", "_").replace("\0", "")
    safe = safe.strip() or "_"
    return safe[:120]


def _file_url(path: Path) -> str:
    return path.resolve().as_uri()


def _mode_type(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISCHR(mode):
        return "char_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    return "unknown"


def _rel_note_path_for(original: Path, mirror_root: Path, is_dir: bool) -> Path:
    if _as_posix(original) == "/":
        return Path("paths") / "ROOT.md"

    parts = [_safe_component(part) for part in original.parts if part != "/"]
    if is_dir:
        return Path("paths").joinpath(*parts, "__dir__.md")
    filename = _safe_component(original.name) + ".file.md"
    return Path("paths").joinpath(*parts[:-1], filename)


def _wiki_link(rel_note: Path, label: str) -> str:
    target = str(rel_note.with_suffix("")).replace(os.sep, "/")
    return f"[[{target}|{label}]]"


def _readable_size(size: int | None) -> str:
    if size is None:
        return "unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.2f} {unit}"


def _frontmatter(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def _hash_note(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class ObsidianOSMirror:
    def __init__(
        self,
        *,
        root: Path,
        vault: Path,
        max_depth: int,
        max_notes: int,
        max_children_per_dir: int,
        exclude_prefixes: set[str],
        stub_prefixes: set[str],
        db_path: Path,
        dry_run: bool = False,
    ) -> None:
        self.root = root.resolve()
        self.vault = vault
        self.mirror_root = vault / "OS_Mirror"
        self.max_depth = max_depth
        self.max_notes = max_notes
        self.max_children_per_dir = max_children_per_dir
        self.exclude_prefixes = exclude_prefixes
        self.stub_prefixes = stub_prefixes
        self.db_path = db_path
        self.dry_run = dry_run
        self.stats = MirrorStats()
        self.generated_notes: list[Path] = []

    def run(self) -> MirrorStats:
        if not self.dry_run:
            self.mirror_root.mkdir(parents=True, exist_ok=True)
            self._init_db()

        self._walk(self.root, depth=0)
        self._write_index_notes()
        return self.stats

    def _walk(self, path: Path, *, depth: int) -> Path | None:
        if self.stats.notes_written >= self.max_notes:
            self.stats.skipped += 1
            return None

        if _is_relative_to(path, self.mirror_root) or _is_relative_to(path, self.vault):
            self.stats.skipped += 1
            return None

        if _matches_prefix(path, self.exclude_prefixes) and path != self.root:
            self.stats.skipped += 1
            return None

        try:
            st = path.lstat()
        except PermissionError:
            self.stats.permission_denied += 1
            return self._write_stub(path, depth=depth, reason="permission_denied")
        except OSError as exc:
            self.stats.errors.append(f"{path}: {exc}")
            return self._write_stub(path, depth=depth, reason=f"os_error: {exc}")

        node_type = _mode_type(st.st_mode)
        if node_type == "directory":
            self.stats.dirs_seen += 1
        elif node_type == "symlink":
            self.stats.symlinks_seen += 1
        else:
            self.stats.files_seen += 1

        if depth > self.max_depth:
            self.stats.skipped += 1
            return self._write_stub(path, depth=depth, reason="max_depth")

        if _matches_prefix(path, self.stub_prefixes) and path != self.root:
            return self._write_stub(path, depth=depth, reason="stub_prefix")

        if node_type == "directory":
            return self._write_directory(path, st, depth=depth)
        return self._write_file(path, st, depth=depth)

    def _sorted_children(self, path: Path) -> tuple[list[Path], bool]:
        try:
            children = list(path.iterdir())
        except PermissionError:
            self.stats.permission_denied += 1
            return [], True
        except OSError as exc:
            self.stats.errors.append(f"{path}: {exc}")
            return [], True

        children.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
        truncated = len(children) > self.max_children_per_dir
        return children[: self.max_children_per_dir], truncated

    def _write_directory(self, path: Path, st: os.stat_result, *, depth: int) -> Path:
        children, truncated = self._sorted_children(path)
        child_links: list[str] = []
        for child in children:
            child_note = self._walk(child, depth=depth + 1)
            if child_note:
                kind = "DIR" if child.is_dir() else "FILE"
                child_links.append(f"- `{kind}` {_wiki_link(child_note, child.name)}")

        rel_note = _rel_note_path_for(path, self.mirror_root, is_dir=True)
        parent_link = ""
        if path.parent != path:
            parent_rel = _rel_note_path_for(path.parent, self.mirror_root, is_dir=True)
            parent_link = f"- Parent: {_wiki_link(parent_rel, str(path.parent))}"

        content = [
            _frontmatter(
                {
                    "nexus_type": "os_mirror_node",
                    "node_kind": "directory",
                    "source_path": str(path),
                    "source_url": _file_url(path),
                    "mapped_at": _now(),
                    "depth": depth,
                    "tags": ["nexus/os-mirror", "nexus/directory"],
                }
            ),
            "",
            f"# {path.name if str(path) != '/' else 'Filesystem Root'}",
            "",
            f"- Source: `{path}`",
            f"- URL: {_file_url(path)}",
            f"- Type: `directory`",
            f"- Mode: `{oct(st.st_mode & 0o777)}`",
            f"- Modified: `{datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')}`",
        ]
        if parent_link:
            content.append(parent_link)
        content.extend(
            [
                "",
                "## Children",
                "",
                *(child_links or ["- No mapped children."]),
            ]
        )
        if truncated:
            content.append(
                f"- Directory listing truncated at {self.max_children_per_dir} entries."
            )
        return self._write_note(rel_note, "\n".join(content), str(path), ["os-mirror", "directory"])

    def _write_file(self, path: Path, st: os.stat_result, *, depth: int) -> Path:
        rel_note = _rel_note_path_for(path, self.mirror_root, is_dir=False)
        parent_rel = _rel_note_path_for(path.parent, self.mirror_root, is_dir=True)
        node_type = _mode_type(st.st_mode)
        target = ""
        if node_type == "symlink":
            try:
                target = os.readlink(path)
            except OSError:
                target = "unreadable"

        content = [
            _frontmatter(
                {
                    "nexus_type": "os_mirror_node",
                    "node_kind": node_type,
                    "source_path": str(path),
                    "source_url": _file_url(path),
                    "mapped_at": _now(),
                    "depth": depth,
                    "tags": ["nexus/os-mirror", f"nexus/{node_type}"],
                }
            ),
            "",
            f"# {path.name}",
            "",
            f"- Source: `{path}`",
            f"- URL: {_file_url(path)}",
            f"- Type: `{node_type}`",
            f"- Size: `{_readable_size(getattr(st, 'st_size', None))}`",
            f"- Mode: `{oct(st.st_mode & 0o777)}`",
            f"- Modified: `{datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')}`",
            f"- Parent: {_wiki_link(parent_rel, str(path.parent))}",
        ]
        if target:
            content.append(f"- Symlink target: `{target}`")
        return self._write_note(rel_note, "\n".join(content), str(path), ["os-mirror", node_type])

    def _write_stub(self, path: Path, *, depth: int, reason: str) -> Path:
        self.stats.stubbed.append(str(path))
        rel_note = _rel_note_path_for(path, self.mirror_root, is_dir=True)
        content = [
            _frontmatter(
                {
                    "nexus_type": "os_mirror_boundary",
                    "node_kind": "boundary",
                    "source_path": str(path),
                    "mapped_at": _now(),
                    "depth": depth,
                    "reason": reason,
                    "tags": ["nexus/os-mirror", "nexus/boundary"],
                }
            ),
            "",
            f"# Boundary: {path}",
            "",
            f"- Source: `{path}`",
            f"- Reason: `{reason}`",
            "- This node is represented as a boundary note to avoid copying, blocking, or exploding runtime pseudo-filesystems.",
        ]
        return self._write_note(rel_note, "\n".join(content), str(path), ["os-mirror", "boundary"])

    def _write_note(self, rel_note: Path, content: str, source_path: str, tags: list[str]) -> Path:
        if self.stats.notes_written >= self.max_notes:
            self.stats.skipped += 1
            return rel_note

        self.stats.notes_written += 1
        self.generated_notes.append(rel_note)
        if self.dry_run:
            return rel_note

        note_path = self.mirror_root / rel_note
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content + "\n", encoding="utf-8")
        self._record_processed_file(note_path, source_path, tags)
        return rel_note

    def _write_index_notes(self) -> None:
        root_rel = _rel_note_path_for(self.root, self.mirror_root, is_dir=True)
        lines = [
            _frontmatter(
                {
                    "nexus_type": "os_mirror_index",
                    "mapped_at": _now(),
                    "root": str(self.root),
                    "tags": ["nexus/os-mirror", "nexus/index"],
                }
            ),
            "",
            "# NEXUS OS Mirror",
            "",
            f"- Root mapped: `{self.root}`",
            f"- Root note: {_wiki_link(root_rel, str(self.root))}",
            f"- Notes written: `{self.stats.notes_written}`",
            f"- Directories seen: `{self.stats.dirs_seen}`",
            f"- Files seen: `{self.stats.files_seen}`",
            f"- Symlinks seen: `{self.stats.symlinks_seen}`",
            f"- Skipped: `{self.stats.skipped}`",
            f"- Permission denied: `{self.stats.permission_denied}`",
            "",
            "## System Areas",
            "",
            "- [[OS_Mirror/areas/System|System]]",
            "- [[OS_Mirror/areas/User_Home|User Home]]",
            "- [[OS_Mirror/areas/Runtime_Boundaries|Runtime Boundaries]]",
            "",
            "## Boundaries",
            "",
            *[f"- `{item}`" for item in sorted(set(self.stats.stubbed))[:200]],
        ]
        self._write_static("NEXUS_OS_INDEX.md", "\n".join(lines))

        self._write_static(
            "areas/System.md",
            "\n".join(
                [
                    "# System",
                    "",
                    "- [[OS_Mirror/paths/etc/__dir__|/etc]]",
                    "- [[OS_Mirror/paths/usr/__dir__|/usr]]",
                    "- [[OS_Mirror/paths/var/__dir__|/var]]",
                    "- [[OS_Mirror/paths/opt/__dir__|/opt]]",
                ]
            ),
        )
        self._write_static(
            "areas/User_Home.md",
            "\n".join(
                [
                    "# User Home",
                    "",
                    "- [[OS_Mirror/paths/home/__dir__|/home]]",
                    "- [[OS_Mirror/paths/home/nexus/__dir__|/home/nexus]]",
                    "- [[OS_Mirror/paths/home/nexus/Documentos/__dir__|Documentos]]",
                ]
            ),
        )
        self._write_static(
            "areas/Runtime_Boundaries.md",
            "\n".join(
                [
                    "# Runtime Boundaries",
                    "",
                    "These paths are represented as boundary notes instead of expanded mirrors.",
                    "",
                    *[f"- `{item}`" for item in sorted(DEFAULT_STUB_PREFIXES)],
                ]
            ),
        )

    def _write_static(self, rel: str, content: str) -> None:
        if self.dry_run:
            return
        path = self.mirror_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        self._record_processed_file(path, str(path), ["os-mirror", "index"])

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    content_hash TEXT NOT NULL,
                    last_modified TIMESTAMP,
                    last_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    detected_tags TEXT,
                    status TEXT DEFAULT 'ok'
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _record_processed_file(self, note_path: Path, source_path: str, tags: list[str]) -> None:
        try:
            content = note_path.read_text(encoding="utf-8")
            content_hash = _hash_note(content)
            tag_json = json.dumps(tags + [source_path], ensure_ascii=False)
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO processed_files
                        (file_path, content_hash, detected_tags, last_modified, status)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'ok')
                    ON CONFLICT(file_path) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        detected_tags = excluded.detected_tags,
                        last_modified = CURRENT_TIMESTAMP,
                        last_processed_at = CURRENT_TIMESTAMP,
                        status = 'ok'
                    """,
                    (str(note_path), content_hash, tag_json),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            self.stats.errors.append(f"db:{note_path}: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mirror OS paths into an Obsidian vault as Markdown index notes."
    )
    parser.add_argument("--root", default="/", help="Root path to mirror.")
    parser.add_argument(
        "--vault",
        default=os.getenv("NEXUS_VAULT_PATH", "/home/nexus/Documentos/Brain"),
        help="Obsidian vault path.",
    )
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--max-notes", type=int, default=25000)
    parser.add_argument("--max-children-per-dir", type=int, default=800)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--db-path",
        default=os.getenv("NEXUS_DB_PATH", str(PROJECT_ROOT / "nexus_events.db")),
    )
    parser.add_argument(
        "--include-runtime",
        action="store_true",
        help="Expand pseudo/runtime filesystems. Not recommended.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    vault = Path(args.vault).expanduser().resolve()
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = (PROJECT_ROOT / db_path).resolve()

    exclude = set()
    stub = set()
    if not args.include_runtime:
        exclude = set(DEFAULT_EXCLUDE_PREFIXES)
        stub = set(DEFAULT_STUB_PREFIXES)

    mirror = ObsidianOSMirror(
        root=root,
        vault=vault,
        max_depth=args.max_depth,
        max_notes=args.max_notes,
        max_children_per_dir=args.max_children_per_dir,
        exclude_prefixes=exclude,
        stub_prefixes=stub,
        db_path=db_path,
        dry_run=args.dry_run,
    )
    stats = mirror.run()
    print(
        json.dumps(
            {
                "vault": str(vault),
                "mirror_root": str(mirror.mirror_root),
                "root": str(root),
                "notes_written": stats.notes_written,
                "dirs_seen": stats.dirs_seen,
                "files_seen": stats.files_seen,
                "symlinks_seen": stats.symlinks_seen,
                "skipped": stats.skipped,
                "permission_denied": stats.permission_denied,
                "errors": stats.errors[:20],
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
