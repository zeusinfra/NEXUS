from __future__ import annotations

import asyncio
import json
import signal
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from nexus_core.events.event_bus import event_bus
from nexus_core.organization.agents import (
    AgentRegistry,
    AgentResult,
    build_default_registry,
)
from nexus_core.organization.blackboard import Blackboard, utc_now
from nexus_core.organization.config import NexusOrgConfig, load_org_config
from nexus_core.organization.continuous import ContinuousAgentRuntime
from nexus_core.organization.health import clear_pid, write_pid
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.organization.observer import ObserverEngine
from nexus_core.organization.replay import ActionReplayBuilder
from nexus_core.organization.runtime import RuntimeEngine
from nexus_core.organization.security import PermissionManager
from nexus_core.organization.swarm import SwarmOrchestrator
from nexus_core.organization.workspace_context import WorkspaceMemory


@dataclass
class DaemonStatus:
    status: str
    mode: str
    agents: int
    tasks: int
    last_heartbeat: str | None


class OrganizationalDaemon:
    """Lightweight persistent core for the NEXUS cognitive company.

    This is the Fase 1 process shell: it owns runtime directories, blackboard
    state, agent registry, heartbeats, and task intake. Command execution stays
    delegated to the existing execution_protocol/policy stack.
    """

    def __init__(
        self,
        config: NexusOrgConfig | None = None,
        *,
        registry: AgentRegistry | None = None,
        blackboard: Blackboard | None = None,
    ) -> None:
        self.config = config or load_org_config()
        self.config.ensure_directories()
        self.memory = OrganizationalMemoryStore(self.config.memory_db_path)
        self.blackboard = blackboard or Blackboard(
            self.config.blackboard_path, memory=self.memory
        )
        if self.blackboard.memory is None:
            self.blackboard.memory = self.memory
        self.registry = registry or build_default_registry()
        self.permissions = PermissionManager(
            self.config, self.blackboard, memory=self.memory
        )
        self.observer = ObserverEngine(memory=self.memory)
        self.continuous_agents = ContinuousAgentRuntime(
            self.registry, self.blackboard, self.memory
        )
        self.swarm = SwarmOrchestrator(self.registry, self.blackboard, self.memory)
        self.workspace_memory = WorkspaceMemory(self.config.project_root)
        self.replay = ActionReplayBuilder(self.memory, self.blackboard)
        self.runtime = RuntimeEngine(
            self.config,
            self.blackboard,
            self.memory,
            ledger=self.permissions.ledger,
            queue=self.permissions.queue,
        )
        self._stop = asyncio.Event()
        self._started = False

    def initialize(self, *, record_event: bool = True) -> None:
        self.config.ensure_directories()
        self.registry.sync_blackboard(self.blackboard)
        self.blackboard.set("mode", self.blackboard.get("mode", "IDLE") or "IDLE")
        self.refresh_workspace_context(record_entry=record_event)
        if record_event:
            self.blackboard.append_event(
                "ORG_DAEMON_INITIALIZED",
                {
                    "agents": self.registry.roles(),
                    "runtime_dir": str(self.config.runtime_dir),
                },
            )

    async def start(self) -> None:
        self.initialize()
        write_pid(self.config.daemon_pid_path)
        self._started = True
        event_bus.start()
        await event_bus.publish_async("ORG_DAEMON_STARTED", {"ts": utc_now()})
        self._install_signal_handlers()
        try:
            while not self._stop.is_set():
                await self.tick()
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.config.heartbeat_interval_s
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            await self.shutdown()

    async def tick(self) -> DaemonStatus:
        observation = self.observer.observe()
        self.blackboard.set("mode", observation.mode)
        agent_ticks = self.continuous_agents.tick_all(observation)
        self.blackboard.heartbeat("online")
        status = self.status()
        await event_bus.publish_async(
            "ORG_DAEMON_HEARTBEAT",
            {
                **asdict(status),
                "observation": observation.to_dict(),
                "agent_ticks": [asdict(tick) for tick in agent_ticks],
            },
        )
        self._write_status_file(status)
        return status

    def observe_once(self) -> dict[str, Any]:
        observation = self.observer.observe()
        self.blackboard.set("mode", observation.mode)
        return observation.to_dict()

    def tick_agents_once(self) -> list[dict[str, Any]]:
        observation = self.observer.observe()
        self.blackboard.set("mode", observation.mode)
        return [asdict(tick) for tick in self.continuous_agents.tick_all(observation)]

    async def shutdown(self) -> None:
        self.blackboard.heartbeat("stopped")
        self.blackboard.append_event("ORG_DAEMON_STOPPED", {"ts": utc_now()})
        self._write_status_file(self.status())
        clear_pid(self.config.daemon_pid_path)
        await event_bus.publish_async("ORG_DAEMON_STOPPED", {"ts": utc_now()})
        event_bus.stop()
        self._started = False

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> DaemonStatus:
        snapshot = self.blackboard.snapshot()
        health = snapshot.get("health", {})
        return DaemonStatus(
            status=health.get("status", "unknown"),
            mode=snapshot.get("mode", "IDLE"),
            agents=len(snapshot.get("agents", {})),
            tasks=len(snapshot.get("tasks", {})),
            last_heartbeat=health.get("last_heartbeat"),
        )

    def memory_status(self) -> dict[str, int]:
        return self.memory.counts()

    def summarize_memory(
        self, *, scope: str = "recent", limit: int = 20
    ) -> dict[str, Any]:
        summary = self.memory.create_summary(scope=scope, limit=limit)
        self.blackboard.append_event(
            "ORG_MEMORY_SUMMARY_CREATED",
            {"summary_id": summary["id"], "scope": scope},
        )
        return summary

    def refresh_workspace_context(self, *, record_entry: bool = True) -> dict[str, Any]:
        context = self.workspace_memory.analyze()
        return self.workspace_memory.persist(
            context,
            blackboard=self.blackboard,
            memory=self.memory,
            record_entry=record_entry,
        )

    def workspace_context(self) -> dict[str, Any]:
        return self.blackboard.get(
            "workspace_context", {}
        ) or self.refresh_workspace_context(record_entry=False)

    def replay_command(self, command_id: str) -> dict[str, Any]:
        return self.replay.command_replay(command_id)

    def replay_task(self, task_id: str) -> dict[str, Any]:
        return self.replay.task_replay(task_id)

    def submit_goal(self, goal: str, *, role: str | None = None) -> AgentResult:
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("goal is required")
        result = self.registry.dispatch(goal, self.blackboard, role=role)
        self.blackboard.append_event(
            "ORG_TASK_ROUTED",
            {
                "goal": goal,
                "agent_role": result.agent_role,
                "status": result.status,
                "task_id": result.task_id,
            },
        )
        return result

    def submit_swarm_objective(
        self,
        goal: str,
        *,
        requested_by: str = "operator",
        autonomy_level: str = "LEVEL_1",
    ) -> dict[str, Any]:
        return self.swarm.submit_objective(
            goal,
            requested_by=requested_by,
            autonomy_level=autonomy_level,
        )

    def propose_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        reason: str = "",
        requested_by: str = "operator",
    ) -> dict[str, Any]:
        return self.permissions.propose_command(
            command,
            cwd=cwd,
            reason=reason,
            requested_by=requested_by,
        )

    def _write_status_file(self, status: DaemonStatus) -> None:
        path = self.config.daemon_status_path
        payload = asdict(status)
        payload["updated_at"] = utc_now()
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2, sort_keys=True)
            f.write("\n")

    def _install_signal_handlers(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.stop)
        except (NotImplementedError, RuntimeError):
            return


async def run_daemon(config_path: str | Path | None = None) -> None:
    daemon = OrganizationalDaemon(load_org_config(config_path))
    await daemon.start()


def status_payload(config_path: str | Path | None = None) -> dict[str, Any]:
    daemon = OrganizationalDaemon(load_org_config(config_path))
    daemon.initialize(record_event=False)
    return asdict(daemon.status())
