"""
ZEUS Cognitive Core — Main Cognitive Loop.

The autonomous brain loop that continuously:
  perceive → update_memory → analyze → generate_goals →
  plan → simulate → act → learn

Runs as an asyncio task with configurable interval and clean shutdown.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, timezone, date
from typing import Any

import psutil

from zeus_core.cognitive.cognitive_db import get_connection, init_cognitive_tables
from zeus_core.cognitive.cognitive_state import cognitive_state_manager
from zeus_core.cognitive.goal_engine import GoalEngine
from zeus_core.cognitive.reflection_engine import ReflectionEngine
from zeus_core.cognitive.planner import CognitivePlanner
from zeus_core.cognitive.simulator import CognitiveSimulator
from zeus_core.cognitive.execution_engine import CognitiveExecutionEngine
from zeus_core.cognitive.learning_engine import CognitiveLearningEngine
from zeus_core.cognitive.user_profile_engine import UserProfileEngine
from zeus_core.cognitive.attention_engine import AttentionEngine
from zeus_core.cognitive.memory_compression import MemoryCompression
from zeus_core.cognitive.priority_orchestrator import PriorityOrchestrator
from zeus_core.cognitive.predictive_engine import PredictiveEngine
from zeus_core.observability import get_logger, log_event, correlation_id_var

logger = get_logger("zeus.cognitive.loop")

# Configuration
from zeus_core.runtime.resource_governor import resource_governor

DB_PATH = os.getenv("NEXUS_DB_PATH", "./zeus_events.db")
MEMORY_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "zeus_memory.db",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CognitiveLoop:
    """The autonomous cognitive loop engine."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self._stop_event = asyncio.Event()
        self._running = False

        # Initialize engines
        self.goal_engine = GoalEngine(db_path=db_path)
        self.reflection_engine = ReflectionEngine(db_path=db_path)
        self.planner = CognitivePlanner(db_path=db_path)
        self.simulator = CognitiveSimulator()
        self.executor = CognitiveExecutionEngine(db_path=db_path)
        self.learner = CognitiveLearningEngine(db_path=db_path)
        self.user_profile = UserProfileEngine(db_path=db_path)
        self.attention_engine = AttentionEngine(db_path=db_path)
        self.memory_compression = MemoryCompression(db_path=db_path)
        self.orchestrator = PriorityOrchestrator(db_path=db_path)
        self.predictive = PredictiveEngine(db_path=db_path)
        from zeus_core.security.privacy_guard import PrivacyGuard

        self.privacy = PrivacyGuard(db_path=db_path)
        from zeus_core.cognitive.self_healing import SelfHealingEngine

        self.self_healing = SelfHealingEngine(db_path=db_path)

        # New Observer Agent
        from zeus_core.core_system import ObserverAgent

        self.observer = ObserverAgent(
            core_path=os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
        )
        self._cycle_count = 0

        # Track daily reflection
        self._last_daily_date: str | None = None

    async def start(self) -> None:
        """Start the cognitive loop."""
        if self._running:
            log_event(logger, 30, "loop_already_running")
            return

        init_cognitive_tables(self.db_path)
        self._running = True
        self._stop_event.clear()
        cognitive_state_manager.mark_started()
        log_event(
            logger,
            20,
            "cognitive_loop_started",
            interval=int(os.getenv("NEXUS_COGNITIVE_INTERVAL_DEFAULT", "20")),
            mode=cognitive_state_manager.state.mode,
        )

        try:
            await self._run()
        finally:
            self._running = False
            cognitive_state_manager.mark_stopped()
            log_event(logger, 20, "cognitive_loop_stopped")

    async def stop(self) -> None:
        """Signal the loop to stop gracefully."""
        log_event(logger, 20, "cognitive_loop_stop_requested")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run(self) -> None:
        """Main loop body."""
        while not self._stop_event.is_set():
            cycle_id = uuid.uuid4().hex[:8]
            token = correlation_id_var.set(f"cog-{cycle_id}")

            try:
                await self._run_cycle(cycle_id)
            except Exception as e:
                cognitive_state_manager.record_error()
                log_event(logger, 40, "cycle_error", cycle_id=cycle_id, error=str(e))
            finally:
                correlation_id_var.reset(token)

            # Wait for next cycle or stop signal
            try:
                # Dynamic Interval
                base_interval = int(os.getenv("NEXUS_COGNITIVE_INTERVAL_DEFAULT", "20"))
                mode = cognitive_state_manager.state.mode
                if mode == "idle":
                    base_interval = int(os.getenv("NEXUS_COGNITIVE_INTERVAL_IDLE", "60"))
                elif mode == "active":
                    base_interval = int(
                        os.getenv("NEXUS_COGNITIVE_INTERVAL_ACTIVE", "10")
                    )

                # Governor override
                interval = resource_governor.get_cognitive_interval(base_interval)

                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval,
                )
                break  # Stop was requested
            except asyncio.TimeoutError:
                continue  # Interval elapsed, run next cycle

    async def _run_cycle(self, cycle_id: str) -> None:
        """Execute one full cognitive cycle."""
        log_event(logger, 20, "cycle_start", cycle_id=cycle_id)
        mode = cognitive_state_manager.state.mode

        # Phase 1: Perceive
        perception = self._perceive()

        # 🛡️ Pillar 3: Privacy Shield (Cognitive Shielding)
        # Mask secrets in perception BEFORE analysis or planning
        perception = self.privacy.sanitize_perception(perception)

        # Phase 2: Update Memory
        memory_update = self._update_memory(perception)

        # Phase 3: Analyze
        analysis = self._analyze(perception, memory_update)

        # Phase 4: Generate Goals (skip in manual mode)
        goals_created = 0
        if mode != "manual":
            goals_created = self._generate_goals(analysis, perception)

        # Phase 5: Orchestrate (Executive Control)
        # 🎯 Pillar 1: Priority Orchestrator
        # Decisions on what to prioritize based on Attention, Resources and Context
        all_pending_goals = self.goal_engine.get_active_goals(limit=20)
        context = {
            "perception": perception,
            "attention": perception.get("attention", {}),
            "temporal": perception.get("temporal", {}),
        }
        orch_result = self.orchestrator.orchestrate(all_pending_goals, context)
        active_goals = orch_result.selected_goals

        # Phase 6-8: Plan → Simulate → Act (only for selected goals)
        actions_executed = 0
        actions_blocked = 0

        if mode != "manual" and active_goals:
            for goal in active_goals:
                try:
                    plan = self.planner.create_plan(goal)
                    sim_result = self.simulator.simulate_plan(plan)
                    results = self.executor.execute_plan(plan, sim_result)

                    # Phase 8: Learn
                    self.learner.learn_from_result(goal, plan, results)
                    delta = self.learner.update_goal_priority(goal, results)
                    if delta:
                        self.goal_engine.adjust_priority(goal.id, delta)

                    # Update goal status
                    successes = sum(1 for r in results if r.status == "success")
                    if successes == len(results) and results:
                        self.goal_engine.update_status(goal.id, "done")
                    elif any(r.status == "failed" for r in results):
                        self.goal_engine.update_status(goal.id, "failed")
                    elif any(r.status == "requires_confirmation" for r in results):
                        self.goal_engine.update_status(goal.id, "requires_confirmation")

                    self.goal_engine.link_plan(goal.id, plan.id)
                    actions_executed += sum(1 for r in results if r.status == "success")
                    actions_blocked += sum(
                        1
                        for r in results
                        if r.status in {"blocked", "requires_confirmation"}
                    )

                except Exception as e:
                    log_event(
                        logger,
                        40,
                        "goal_processing_error",
                        goal_id=goal.id,
                        error=str(e),
                    )
                    self.goal_engine.update_status(goal.id, "failed")

        # Cycle reflection
        self.reflection_engine.cycle_reflection(
            cycle_id=cycle_id,
            perception_summary=perception.get("summary", ""),
            analysis_summary=analysis.get("summary", ""),
            goals_created=goals_created,
            actions_executed=actions_executed,
            actions_blocked=actions_blocked,
        )

        # Check for daily reflection
        today = date.today().isoformat()
        if self._last_daily_date != today:
            self._try_daily_reflection(today)

        # Update cognitive state
        counts = self.goal_engine.count_by_status()
        active = counts.get("pending", 0) + counts.get("planned", 0)
        blocked = counts.get("blocked", 0) + counts.get("requires_confirmation", 0)
        pending_conf = len(self.executor.get_pending_confirmations())

        health = self._calculate_health(perception, analysis)

        cognitive_state_manager.mark_cycle_complete(
            active_goals=active,
            blocked_goals=blocked,
            pending_confirmations=pending_conf,
            focus=self._goal_value(active_goals[0], "title") if active_goals else None,
            health_score=health,
            attention=perception.get("attention"),
            active_goals_list=[
                {
                    "title": self._goal_value(g, "title"),
                    "type": self._goal_value(g, "type"),
                }
                for g in orch_result.selected_goals
            ],
            privacy_status={
                "shield": "active",
                "masked_count": self.privacy.session_masked_count,
            },
        )

        log_event(
            logger,
            20,
            "cycle_complete",
            cycle_id=cycle_id,
            goals_created=goals_created,
            actions_executed=actions_executed,
            actions_blocked=actions_blocked,
            health=health,
        )

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _perceive(self) -> dict:
        """Collect system state, events, and memory signals."""
        perception: dict[str, Any] = {
            "timestamp": _now_iso(),
            "summary": "",
        }

        # System resources
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            perception["system"] = {
                "cpu_percent": cpu,
                "ram_percent": ram,
                "disk_percent": disk,
            }
        except Exception:
            perception["system"] = {}

        # Recent events from SQLite
        try:
            with get_connection(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT event_type, source, status, COUNT(*) as cnt "
                    "FROM events WHERE created_at > datetime('now', '-5 minutes') "
                    "GROUP BY event_type, source, status ORDER BY cnt DESC LIMIT 20"
                ).fetchall()
                perception["recent_events"] = [dict(r) for r in rows]
        except Exception:
            perception["recent_events"] = []

        # Pending events
        try:
            with get_connection(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM events WHERE status = 'pending'"
                ).fetchone()
                perception["pending_events"] = row["cnt"] if row else 0
        except Exception:
            perception["pending_events"] = 0

        # Memory stats
        try:
            mem_conn = sqlite3.connect(MEMORY_DB_PATH)
            mem_conn.row_factory = sqlite3.Row
            c = mem_conn.cursor()
            c.execute("SELECT COUNT(*) as cnt FROM nodes")
            node_count = c.fetchone()["cnt"]
            c.execute("SELECT path, weight FROM nodes ORDER BY weight DESC LIMIT 5")
            hot_nodes = [
                {"path": r["path"], "weight": r["weight"]} for r in c.fetchall()
            ]
            mem_conn.close()
            perception["memory"] = {
                "total_nodes": node_count,
                "hot_nodes": hot_nodes,
            }
        except Exception:
            perception["memory"] = {"total_nodes": 0, "hot_nodes": []}

        # Attention and Context
        try:
            attention = self.attention_engine.get_current_attention()
            perception["attention"] = attention.to_dict()
            perception["temporal"] = (
                self.user_profile.build_temporal_context().to_dict()
            )
            perception["user_session"] = self.user_profile.get_current_session_summary()
        except Exception:
            perception["attention"] = {"state": "idle"}
            perception["temporal"] = {}
            perception["user_session"] = {"active": False}

        # Visual Context (Pillar 1)
        # Capture screen every 10 cycles (approx 5 mins at 30s interval) or if user is active
        self._cycle_count += 1
        if self._cycle_count % 10 == 0 or perception.get("user_session", {}).get(
            "active"
        ):
            try:
                # Fazemos a observação em uma thread separada para não travar o loop
                visual_desc = self.observer.observe_screen(
                    self.goal_engine.blackboard,
                    question="Descreva brevemente as janelas ativas e o que o usuário parece estar fazendo.",
                )
                perception["visual_context"] = visual_desc
            except Exception as e:
                logger.error(f"Vision error in loop: {e}")

        # Silent Mode / Deep Work Detection (Phase 4)
        active = perception.get("user_session", {}).get("active", False)
        # Se o usuário está ativo por mais de 10 min com janelas de 'dev', entramos em Deep Work
        is_dev_window = any(
            x in str(perception.get("visual_context", "")).lower()
            for x in ["code", "terminal", "nvim", "cursor"]
        )
        if active and is_dev_window:
            perception["cognitive_mode"] = "deep_work"
            logger.info("Deep Work detected. Activating Cognitive Firewall.")
        else:
            perception["cognitive_mode"] = "nominal"

        # Build summary
        sys = perception.get("system", {})
        summary_parts = []
        if sys.get("cpu_percent", 0) > 80:
            summary_parts.append(f"CPU alta ({sys['cpu_percent']}%)")
        if sys.get("ram_percent", 0) > 85:
            summary_parts.append(f"RAM alta ({sys['ram_percent']}%)")
        if perception.get("pending_events", 0) > 50:
            summary_parts.append(f"{perception['pending_events']} eventos pendentes")
        perception["summary"] = (
            "; ".join(summary_parts) if summary_parts else "Sistema estável"
        )

        return perception

    def _update_memory(self, perception: dict) -> dict:
        """Register relevant events and update memory weights."""
        return {
            "events_registered": len(perception.get("recent_events", [])),
            "memory_nodes": perception.get("memory", {}).get("total_nodes", 0),
        }

    def _analyze(self, perception: dict, memory_update: dict) -> dict:
        """Detect patterns, anomalies, and opportunities."""
        analysis: dict[str, Any] = {
            "patterns": [],
            "anomalies": [],
            "opportunities": [],
            "importance_score": 0,
            "summary": "",
        }

        sys = perception.get("system", {})
        cpu = sys.get("cpu_percent", 0)
        ram = sys.get("ram_percent", 0)
        disk = sys.get("disk_percent", 0)

        # Resource anomalies
        if cpu > 90:
            analysis["anomalies"].append({"type": "high_cpu", "value": cpu})
            analysis["importance_score"] += 30
        elif cpu > 70:
            analysis["patterns"].append({"type": "elevated_cpu", "value": cpu})
            analysis["importance_score"] += 10

        if ram > 90:
            analysis["anomalies"].append({"type": "high_ram", "value": ram})
            analysis["importance_score"] += 30
        elif ram > 75:
            analysis["patterns"].append({"type": "elevated_ram", "value": ram})
            analysis["importance_score"] += 10

        if disk > 90:
            analysis["anomalies"].append({"type": "high_disk", "value": disk})
            analysis["importance_score"] += 20

        # Swap pressure
        swap_info = psutil.swap_memory()
        swap = swap_info.percent if swap_info.total > 0 else 0
        if swap > 50:
            analysis["anomalies"].append({"type": "high_swap", "value": swap})
            analysis["importance_score"] += 25

        # Event anomalies
        pending = perception.get("pending_events", 0)
        if pending > 100:
            analysis["anomalies"].append({"type": "event_backlog", "count": pending})
            analysis["importance_score"] += 15

        # Hot node detection (files accessed too frequently)
        hot_nodes = perception.get("memory", {}).get("hot_nodes", [])
        for node in hot_nodes:
            if node.get("weight", 0) > 500:
                analysis["patterns"].append(
                    {
                        "type": "hot_node",
                        "path": node["path"],
                        "weight": node["weight"],
                    }
                )

        # Opportunities
        if not analysis["anomalies"] and not analysis["patterns"]:
            analysis["opportunities"].append(
                "Sistema ocioso — boa hora para reflexão profunda"
            )

        # User-Aware Analysis
        temporal = perception.get("temporal", {})
        if temporal.get("is_deep_focus"):
            # Reduce importance score during deep focus to avoid interrupting user
            analysis["importance_score"] = int(analysis["importance_score"] * 0.5)
            analysis["patterns"].append(
                {"type": "deep_focus_active", "label": "Usuário em foco profundo"}
            )

        if temporal.get("is_late_night"):
            analysis["patterns"].append(
                {
                    "type": "late_night_active",
                    "label": "Operação noturna (baixa prioridade)",
                }
            )

        # Modulate by Attention
        attention = perception.get("attention", {})
        bias = attention.get("priority_bias", {})

        # Performance/System bias
        if analysis["anomalies"] or analysis["patterns"]:
            analysis["importance_score"] *= bias.get("performance", 1.0)

        # Suppression of noise
        if (
            attention.get("suggestion_suppression")
            and analysis["importance_score"] < 50
        ):
            analysis["importance_score"] *= 0.5
            analysis["summary"] = "Ruído suprimido por foco ativo."
        elif not analysis["summary"]:
            if analysis["importance_score"] > 60:
                analysis["summary"] = "Anomalias críticas detectadas"
            elif analysis["importance_score"] > 20:
                analysis["summary"] = "Padrões operacionais detectados"
            else:
                analysis["summary"] = "Estado nominal"

        # Self-Healing Analysis (Pillar 3)
        issues = self.self_healing.scan_for_issues()
        if issues:
            analysis["anomalies"].append(
                {"type": "system_errors", "count": len(issues)}
            )
            analysis["importance_score"] += 20

        return analysis

    def _generate_goals(self, analysis: dict, perception: dict | None = None) -> int:
        """Create goals from analysis findings."""
        created = 0
        is_late_night = False
        if perception:
            is_late_night = perception.get("temporal", {}).get("is_late_night", False)

        for anomaly in analysis.get("anomalies", []):
            atype = anomaly.get("type", "")
            goal = None

            if atype == "high_cpu":
                goal = self.goal_engine.create_goal(
                    f"Investigar uso elevado de CPU ({anomaly.get('value')}%)",
                    goal_type="performance",
                    origin="system_analysis",
                    priority=75,
                    risk="low",
                    evidence=[anomaly],
                )
            elif atype == "high_ram":
                goal = self.goal_engine.create_goal(
                    f"Reduzir uso excessivo de RAM ({anomaly.get('value')}%)",
                    goal_type="performance",
                    origin="system_analysis",
                    priority=80,
                    risk="medium",
                    evidence=[anomaly],
                )
            elif atype == "high_disk":
                goal = self.goal_engine.create_goal(
                    "Investigar uso elevado de disco",
                    goal_type="maintenance",
                    origin="system_analysis",
                    priority=60,
                    risk="low",
                    evidence=[anomaly],
                )
            elif atype == "event_backlog":
                goal = self.goal_engine.create_goal(
                    f"Processar backlog de {anomaly.get('count')} eventos pendentes",
                    goal_type="operational",
                    origin="system_analysis",
                    priority=65,
                    risk="low",
                    evidence=[anomaly],
                )
            elif atype == "high_swap":
                goal = self.goal_engine.create_goal(
                    f"Reduzir uso de SWAP e pressão de memória ({anomaly.get('value')}%)",
                    goal_type="performance",
                    origin="system_analysis",
                    priority=85,
                    risk="medium",
                    evidence=[anomaly],
                )

            if goal:
                # Late night deferral logic (Question B from plan)
                if is_late_night and goal.type != "security":
                    self.goal_engine.update_status(goal.id, "deferred")
                    log_event(logger, 20, "goal_deferred_late_night", goal_id=goal.id)

                created += 1

        # 🔮 Pillar 2: Predictive Engine (Anticipation)
        # Generate proactive goals based on habits and workflows
        profile_summary = self.user_profile.get_profile_summary()
        proactive_suggestions = self.predictive.anticipate(profile_summary, perception)
        for suggestion in proactive_suggestions:
            # Check if similar proactive goal already exists to avoid duplication
            # (Simplified for this version)
            goal = self.goal_engine.create_goal(
                suggestion["title"],
                goal_type=suggestion["type"],
                origin="predictive_engine",
                priority=suggestion["priority"],
                description=suggestion["description"],
                risk=suggestion["risk"],
            )
            if goal:
                created += 1

        # Check for repeated failures → create investigation goal
        repeated = self.learner.detect_repeated_failures(threshold=3)
        for failure in repeated:
            goal = self.goal_engine.create_goal(
                f"Investigar falha recorrente: {failure['lesson'][:80]}",
                goal_type="cognitive",
                origin="reflection",
                priority=70,
                risk="low",
                evidence=[failure],
            )
            if goal:
                created += 1

        return created

    def _try_daily_reflection(self, today: str) -> None:
        """Generate daily reflection if not already done today."""
        try:
            state = cognitive_state_manager.state

            # Build user summary for reflection
            profile = self.user_profile.build_temporal_context()
            user_summary = f"Sessão de {profile.session_duration_min}min ativa. Hábitos: {', '.join(profile.expected_habits)}."

            self.reflection_engine.daily_reflection(
                cycle_count=state.cycle_count,
                health_score=state.health_score,
                user_summary=user_summary,
            )

            # Run Memory Compression (Pillar 3)
            self.memory_compression.compress_all()

            self._last_daily_date = today
            log_event(logger, 20, "daily_reflection_generated", date=today)

            # Also export active goals to Obsidian
            active = self.goal_engine.get_active_goals()
            self.reflection_engine.export_goals_to_obsidian(active)

            # User Profile Intelligence Synthesis (once per day)
            self.user_profile.synthesize_habits()
            self.user_profile.detect_workflows()
            self.user_profile.export_profile_to_obsidian()
        except Exception as e:
            log_event(logger, 40, "daily_reflection_error", error=str(e))

    def _calculate_health(self, perception: dict, analysis: dict) -> int:
        """Calculate system health score (0-100)."""
        score = 100
        sys = perception.get("system", {})

        # Resource penalties
        cpu = sys.get("cpu_percent", 0)
        ram = sys.get("ram_percent", 0)
        if cpu > 90:
            score -= 25
        elif cpu > 70:
            score -= 10
        if ram > 90:
            score -= 25
        elif ram > 75:
            score -= 10

        # Anomaly penalties
        anomaly_count = len(analysis.get("anomalies", []))
        score -= anomaly_count * 5

        # Error penalty
        score -= min(20, cognitive_state_manager.state.error_count * 2)

        return max(0, min(100, score))

    @staticmethod
    def _goal_value(goal: Any, key: str, default: Any = None) -> Any:
        if isinstance(goal, dict):
            return goal.get(key, default)
        return getattr(goal, key, default)

    async def run_single_cycle(self) -> None:
        """Run a single cycle (for testing)."""
        cycle_id = uuid.uuid4().hex[:8]
        token = correlation_id_var.set(f"cog-{cycle_id}")
        try:
            await self._run_cycle(cycle_id)
        finally:
            correlation_id_var.reset(token)
