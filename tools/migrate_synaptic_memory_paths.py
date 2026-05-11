#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _memory_path() -> Path:
    return _project_root() / "data" / "synaptic_memory.json"


def _backup(path: Path, suffix: str) -> Path:
    ts = int(time.time())
    backup = path.with_suffix(path.suffix + f".{suffix}.{ts}")
    backup.write_bytes(path.read_bytes())
    return backup


def _update_path(p: str) -> str:
    if not isinstance(p, str) or not p:
        return p
    # core_modules -> zeus_core
    p = p.replace("/core_modules/", "/zeus_core/")
    # antigos entrypoints
    p = p.replace("/web_gui.py", "/apps/web_gui.py")
    p = p.replace("/zeus_v4.py", "/apps/zeus_v4.py")
    p = p.replace("/zeus_evolution.py", "/apps/zeus_evolution.py")
    return p


def main() -> int:
    mem_path = _memory_path()
    if not mem_path.exists():
        print(f"[migrate] memory file not found: {mem_path}")
        return 0

    raw = mem_path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except Exception as e:
        backup = _backup(mem_path, "corrupt")
        mem_path.write_text("{}", encoding="utf-8")
        print(f"[migrate] synaptic_memory.json inválido: {e}")
        print(f"[migrate] backup: {backup}")
        print("[migrate] reset: wrote empty {}")
        return 0

    if not isinstance(data, dict):
        backup = _backup(mem_path, "unexpected")
        mem_path.write_text("{}", encoding="utf-8")
        print(f"[migrate] conteúdo inesperado (não-dict). backup: {backup}")
        return 0

    updated: dict[str, dict] = {}
    for path, meta in data.items():
        if not isinstance(meta, dict):
            meta = {}
        new_path = _update_path(path)
        conns = meta.get("connections", [])
        if not isinstance(conns, list):
            conns = []
        new_conns = [_update_path(c) for c in conns if isinstance(c, str)]
        updated[new_path] = {
            "weight": int(meta.get("weight", 0) or 0),
            "connections": new_conns,
        }

    backup = _backup(mem_path, "pre_migrate")
    mem_path.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[migrate] ok. backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
