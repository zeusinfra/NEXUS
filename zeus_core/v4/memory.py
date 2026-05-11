from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zeus_core.vector_memory import VectorMemory
from zeus_core.v4.types import Event, Situation


@dataclass(slots=True)
class ShortTermMemory:
    max_events: int = 120
    events: list[Event] = field(default_factory=list)

    def add(self, evs: list[Event]) -> None:
        self.events.extend(evs)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]

    def context_snippet(self) -> str:
        tail = self.events[-12:]
        lines = [f"- [{e.kind}] {e.summary}" for e in tail]
        return "\n".join(lines)


@dataclass(slots=True)
class MidTermMemory:
    # pesos simples por label de situação
    counters: dict[str, int] = field(default_factory=dict)

    def note(self, situation: Situation) -> None:
        key = situation.label
        self.counters[key] = int(self.counters.get(key, 0)) + 1

    def suggest_goals(self) -> list[tuple[str, float]]:
        suggestions: list[tuple[str, float]] = []
        for label, count in sorted(
            self.counters.items(), key=lambda kv: kv[1], reverse=True
        )[:5]:
            if count >= 4:
                suggestions.append(
                    (f"Reduzir recorrência: {label}", min(1.0, 0.55 + count / 20))
                )
        return suggestions


class LongTermMemory:
    def __init__(self, *, storage_file: str):
        self.vec = VectorMemory(storage_file=storage_file)

    def index_episode(self, key: str, text: str) -> None:
        if os.getenv("ZEUS_V4_EMBEDDINGS", "1").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return
        # VectorMemory atual indexa arquivo. Para manter compatível, salvamos episódio em arquivo e indexamos.
        if not text.strip():
            return
        base = Path(os.getenv("ZEUS_V4_EPISODES_DIR", "scratch/v4_episodes")).resolve()
        base.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)[
            :80
        ]
        path = base / f"{int(time.time())}_{safe}.txt"
        path.write_text(text, encoding="utf-8")
        try:
            self.vec.index_file(str(path))
        except Exception:
            return


class EpisodeLog:
    def __init__(self, *, path: str):
        self.path = Path(path)

    def append(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
