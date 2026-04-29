from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from zeus_core.v4.types import Goal


def _clamp01(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, v))


class GoalsEngine:
    def __init__(self, *, storage_path: str):
        self.path = Path(storage_path)
        self.goals: dict[str, Goal] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.goals = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.goals = {}
            return
        if not isinstance(data, list):
            self.goals = {}
            return
        loaded: dict[str, Goal] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("id") or "").strip()
            if not gid:
                continue
            loaded[gid] = Goal(
                id=gid,
                descricao=str(item.get("descricao") or "").strip() or gid,
                prioridade=float(item.get("prioridade") or 0.5),
                estado=(item.get("estado") or "ativo"),
                progresso=_clamp01(item.get("progresso") or 0.0),
                meta=item.get("meta") if isinstance(item.get("meta"), dict) else {},
            )
        self.goals = loaded

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(goal) for goal in self.list()]
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def list(self) -> list[Goal]:
        return sorted(self.goals.values(), key=lambda g: (g.estado != "ativo", -g.prioridade))

    def upsert(self, goal: Goal) -> None:
        self.goals[goal.id] = goal

    def get_active(self) -> list[Goal]:
        return [g for g in self.list() if g.estado == "ativo"]

    def ensure_default_goals(self) -> None:
        if self.goals:
            return
        self.upsert(
            Goal(
                id="goal_001",
                descricao="Otimizar workflow do usuário",
                prioridade=0.9,
                estado="ativo",
                progresso=0.1,
                meta={"created_ts": time.time(), "source": "bootstrap"},
            )
        )
        self.save()

    def update_progress(self, goal_id: str, delta: float) -> None:
        goal = self.goals.get(goal_id)
        if not goal:
            return
        goal.progresso = _clamp01(goal.progresso + float(delta or 0.0))
        if goal.progresso >= 1.0 and goal.estado == "ativo":
            goal.estado = "concluido"

    def auto_create_from_patterns(self, suggestions: Iterable[tuple[str, float]]) -> list[Goal]:
        created: list[Goal] = []
        for desc, prio in suggestions:
            desc = str(desc or "").strip()
            if not desc:
                continue
            gid = f"goal_auto_{abs(hash(desc)) % 100000:05d}"
            if gid in self.goals:
                continue
            g = Goal(id=gid, descricao=desc, prioridade=_clamp01(prio), estado="ativo", progresso=0.0, meta={"source": "pattern"})
            self.upsert(g)
            created.append(g)
        if created:
            self.save()
        return created
