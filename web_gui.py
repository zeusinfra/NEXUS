"""Compatibility helpers for legacy ``import web_gui`` callers.

The FastAPI application lives in ``apps.web_gui`` and performs heavyweight
service initialization at import time. Regression tests and older scripts only
need the in-memory synaptic summary helpers, so this module keeps that legacy
surface lightweight and dependency-free.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


synaptic_memory: dict[str, dict[str, Any]] = {}


def ensure_memory_entry(path: str) -> dict[str, Any]:
    """Return a normalized synaptic-memory entry for ``path``."""
    entry = synaptic_memory.get(path)
    if not isinstance(entry, dict):
        entry = {"weight": 0, "connections": set()}
    else:
        try:
            weight = int(entry.get("weight", 0))
        except (TypeError, ValueError):
            weight = 0

        connections = entry.get("connections", set())
        if isinstance(connections, set):
            normalized_connections = connections
        elif isinstance(connections, Iterable) and not isinstance(
            connections, (str, bytes)
        ):
            normalized_connections = set(connections)
        else:
            normalized_connections = set()

        entry = {"weight": weight, "connections": normalized_connections}

    synaptic_memory[path] = entry
    return entry


def build_memory_summary() -> dict[str, Any]:
    """Build a compact summary for the legacy in-memory synaptic graph."""
    normalized_entries = {
        path: ensure_memory_entry(path) for path in list(synaptic_memory.keys())
    }
    learned_paths = len(normalized_entries)
    connection_total = sum(
        len(entry["connections"]) for entry in normalized_entries.values()
    )
    hottest_path = None
    hottest_weight = 0

    if normalized_entries:
        hottest_path, hottest_entry = max(
            normalized_entries.items(),
            key=lambda item: item[1]["weight"],
        )
        hottest_weight = hottest_entry["weight"]

    recall_index = min(
        100, round((connection_total * 2 + hottest_weight) / max(1, learned_paths))
    )
    memory_density = round(connection_total / max(1, learned_paths), 2)
    return {
        "learned_paths": learned_paths,
        "connection_total": connection_total,
        "hottest_path": hottest_path,
        "hottest_weight": hottest_weight,
        "recall_index": recall_index,
        "memory_density": memory_density,
    }
