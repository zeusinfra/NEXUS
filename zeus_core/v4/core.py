from __future__ import annotations

import asyncio
import os
import time
from dataclasses import asdict
from typing import Any

from zeus_core.v4.executor import ShadowExecutor
from zeus_core.v4.goals import GoalsEngine
from zeus_core.v4.memory import (
    EpisodeLog,
    LongTermMemory,
    MidTermMemory,
    ShortTermMemory,
)
from zeus_core.v4.planner import MultiStepPlanner
from zeus_core.v4.sensors import (
    FilePollSensor,
    OsMetricsSensor,
    UserInboxSensor,
    default_roots,
)
from zeus_core.v4.types import AutonomyMode, DecisionType, Event, Goal, Situation


def _now() -> float:
    return time.time()


def _env_mode() -> AutonomyMode:
    m = os.getenv("NEXUS_MODE", os.getenv("NEXUS_V4_MODE", "SAFE")).strip().upper()
    return (
        AutonomyMode(m) if m in {e.value for e in AutonomyMode} else AutonomyMode.SAFE
    )


class ZeusCognitiveCoreV4:
    def __init__(self):
        self.mode = _env_mode()
        self.short = ShortTermMemory()
        self.mid = MidTermMemory()
        self.long = LongTermMemory(
            storage_file=os.getenv("NEXUS_V4_VECTOR_FILE", "data/vector_memory.json")
        )
        self.episodes = EpisodeLog(
            path=os.getenv("NEXUS_V4_EPISODES_LOG", "logs/v4_episodes.jsonl")
        )

        self.goals = GoalsEngine(
            storage_path=os.getenv("NEXUS_V4_GOALS_FILE", "configs/goals_v4.json")
        )
        self.goals.ensure_default_goals()

        self.planner = MultiStepPlanner(
            llm_enabled=os.getenv("NEXUS_V4_LLM", "1").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.exec = ShadowExecutor(mode=self.mode)

        roots = default_roots()
        self.sensors = [
            OsMetricsSensor(),
            FilePollSensor(roots),
            UserInboxSensor(os.getenv("NEXUS_V4_INBOX_FILE", "scratch/v4_inbox.txt")),
        ]

        self.loop_delay_s = float(os.getenv("NEXUS_V4_LOOP_DELAY", "1.0"))

    async def run_forever(self) -> None:
        max_cycles_env = os.getenv("NEXUS_V4_MAX_CYCLES", "").strip()
        max_cycles = int(max_cycles_env) if max_cycles_env.isdigit() else None
        cycle = 0

        self._debug("CORE", f"ZEUS v4 online mode={self.mode.value}")
        while True:
            cycle += 1
            await self._cycle(cycle)
            if max_cycles is not None and cycle >= max_cycles:
                self._debug(
                    "CORE", f"Max cycles reached ({max_cycles}). Exiting (test mode)."
                )
                return
            await asyncio.sleep(self.loop_delay_s)

    async def _cycle(self, cycle: int) -> None:
        # 1) PERCEPÇÃO
        events = self._perceive()
        self.short.add(events)

        # 2) INTERPRETAÇÃO
        situation = self._interpret(events)
        self.mid.note(situation)

        # Se não há sinais relevantes, apenas mantém o loop vivo.
        top_rel = max((e.relevance for e in events), default=0.0)
        if (
            top_rel < float(os.getenv("NEXUS_V4_MIN_RELEVANCE", "0.18"))
            and situation.label == "idle"
        ):
            self._debug("WAIT", "Sem sinais relevantes. Mantendo vigilância.")
            return

        # 2.1) GOALS auto-create (mid-term)
        self.goals.auto_create_from_patterns(self.mid.suggest_goals())

        # 3) PLANEJAMENTO
        goal = self._select_goal()
        plan = self.planner.plan(goal, context=self._context_string(situation))

        # 4) DECISÃO
        decision = self.exec.decide(plan)
        self._debug(
            "DECIDE",
            f"{decision.kind.value} reward≈{decision.expected_reward:.3f} reason={decision.reason}",
        )
        if decision.kind == DecisionType.WAIT:
            return
        if decision.kind == DecisionType.CONFIRM:
            self._debug(
                "GUARD",
                f"CONFIRM required for plan goal={plan.goal_id} risk={plan.estimated_risk.value}",
            )
            return

        # 5) EXECUÇÃO (shadow always)
        results, reward = await self.exec.run_plan_shadow(plan)

        # 6) AVALIAÇÃO (reward)
        self._debug(
            "REWARD",
            f"total={reward.total():.3f} success={reward.success} impact={reward.impact:.2f} risk={reward.risk:.2f} cost={reward.cost:.2f}",
        )

        # 7) APRENDIZADO (memória + objetivos)
        self._learn(goal, plan, situation, results, reward.total())

        # progresso simples: se sucesso, avança; se falha, retrocede levemente
        self.goals.update_progress(
            goal.id, delta=0.05 if reward.success >= 1.0 else -0.01
        )
        self.goals.save()

    def _perceive(self) -> list[Event]:
        evs: list[Event] = []
        for sensor in self.sensors:
            try:
                evs.extend(sensor.poll())
            except Exception:
                continue
        evs.sort(key=lambda e: e.relevance, reverse=True)
        return evs[:40]

    def _interpret(self, events: list[Event]) -> Situation:
        pressure = None
        for ev in events:
            if ev.kind == "os":
                pressure = ev.data.get("pressure")
                break
        label = "idle"
        if any(ev.kind == "user" for ev in events):
            label = "user_request"
        elif pressure in {"ACTIVE", "CRITICAL"}:
            label = f"os_pressure_{str(pressure).lower()}"
        elif any(ev.kind == "fs" for ev in events):
            label = "active_editing"
        return Situation(
            ts=_now(), label=label, events=events, context={"pressure": pressure}
        )

    def _select_goal(self) -> Goal:
        active = self.goals.get_active()
        if not active:
            g = Goal(
                id="goal_001", descricao="Otimizar workflow do usuário", prioridade=0.9
            )
            self.goals.upsert(g)
            self.goals.save()
            return g
        return active[0]

    def _context_string(self, situation: Situation) -> str:
        return (
            f"Modo: {self.mode.value}\n"
            f"Situação: {situation.label}\n"
            f"Eventos recentes:\n{self.short.context_snippet()}\n"
        )

    def _learn(
        self, goal: Goal, plan, situation: Situation, results, reward_total: float
    ) -> None:
        payload: dict[str, Any] = {
            "ts": _now(),
            "mode": self.mode.value,
            "goal": asdict(goal),
            "situation": {
                "label": situation.label,
                "pressure": situation.context.get("pressure"),
            },
            "plan": {
                "objective": plan.objective,
                "estimated_risk": plan.estimated_risk.value,
                "expected_impact": plan.expected_impact,
                "steps": [
                    {
                        "step": s.step,
                        "description": s.description,
                        "action": s.action,
                        "risk": s.estimated_risk.value,
                        "impact": s.estimated_impact,
                    }
                    for s in plan.steps
                ],
            },
            "results": [asdict(r) for r in results],
            "reward": reward_total,
        }
        self.episodes.append(payload)
        text = f"Goal: {goal.descricao}\nSituation: {situation.label}\nPlan: {plan.objective}\nReward: {reward_total}\n"
        self.long.index_episode(goal.id, text)

    def _debug(self, stage: str, msg: str) -> None:
        if os.getenv("NEXUS_V4_DEBUG", "1").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return
        print(f"[NEXUS v4][{stage}] {msg}")
