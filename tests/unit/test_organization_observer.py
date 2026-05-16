from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from nexus_core.organization.agents import build_default_registry
from nexus_core.organization.blackboard import Blackboard
from nexus_core.organization.config import NexusOrgConfig
from nexus_core.organization.continuous import ContinuousAgentRuntime
from nexus_core.organization.daemon import OrganizationalDaemon
from nexus_core.organization.memory import OrganizationalMemoryStore
from nexus_core.organization.observer import ObserverEngine


@dataclass
class FakeAttentionSnapshot:
    state: str
    active_window: str | None
    triggers: list[str]

    def to_dict(self):
        return {
            "state": self.state,
            "active_window": self.active_window,
            "triggers": self.triggers,
        }


class FakeAttention:
    def __init__(self, state="idle", active_window=None):
        self.state = state
        self.active_window = active_window

    def get_current_attention(self):
        return FakeAttentionSnapshot(
            state=self.state,
            active_window=self.active_window,
            triggers=["fake attention"],
        )


def test_observer_detects_development_from_window(tmp_path):
    store = OrganizationalMemoryStore(tmp_path / "org.sqlite3")
    observer = ObserverEngine(
        memory=store,
        attention=FakeAttention("idle", "Visual Studio Code - NEXUS"),
        process_provider=lambda: [{"pid": 1, "name": "code"}],
    )

    with (
        patch("nexus_core.organization.observer.psutil.cpu_percent", return_value=10),
        patch(
            "nexus_core.organization.observer.psutil.virtual_memory",
            return_value=type("VM", (), {"percent": 40})(),
        ),
        patch(
            "nexus_core.organization.observer.psutil.disk_usage",
            return_value=type("DU", (), {"percent": 50})(),
        ),
    ):
        snapshot = observer.observe()

    assert snapshot.mode == "DEVELOPMENT"
    assert snapshot.confidence >= 0.8
    assert store.list_observations()[0]["mode"] == "DEVELOPMENT"


def test_observer_detects_maintenance_from_pressure(tmp_path):
    observer = ObserverEngine(
        attention=FakeAttention("idle", None),
        process_provider=lambda: [],
    )

    with (
        patch("nexus_core.organization.observer.psutil.cpu_percent", return_value=91),
        patch(
            "nexus_core.organization.observer.psutil.virtual_memory",
            return_value=type("VM", (), {"percent": 50})(),
        ),
        patch(
            "nexus_core.organization.observer.psutil.disk_usage",
            return_value=type("DU", (), {"percent": 50})(),
        ),
    ):
        snapshot = observer.observe()

    assert snapshot.mode == "MAINTENANCE"
    assert "High resource pressure detected" in snapshot.triggers


def test_continuous_agents_tick_and_update_blackboard(tmp_path):
    store = OrganizationalMemoryStore(tmp_path / "org.sqlite3")
    blackboard = Blackboard(tmp_path / "blackboard.json", memory=store)
    registry = build_default_registry()
    registry.sync_blackboard(blackboard)
    observer = ObserverEngine(
        attention=FakeAttention("development", "Terminal - pytest"),
        process_provider=lambda: [{"pid": 2, "name": "pytest"}],
        memory=store,
    )
    runtime = ContinuousAgentRuntime(registry, blackboard, store)

    with (
        patch("nexus_core.organization.observer.psutil.cpu_percent", return_value=12),
        patch(
            "nexus_core.organization.observer.psutil.virtual_memory",
            return_value=type("VM", (), {"percent": 35})(),
        ),
        patch(
            "nexus_core.organization.observer.psutil.disk_usage",
            return_value=type("DU", (), {"percent": 50})(),
        ),
    ):
        observation = observer.observe()
    ticks = runtime.tick_all(observation)

    assert len(ticks) == 9
    agents = blackboard.snapshot()["agents"]
    assert agents["observer"]["runtime"]["status"] == "observing"
    assert agents["coder"]["runtime"]["status"] == "active"
    assert store.list_agent_ticks(agent_role="coder")[0]["mode"] == "DEVELOPMENT"


def test_daemon_tick_records_observation_and_agent_ticks(tmp_path):
    config = NexusOrgConfig.from_mapping({"project_root": str(tmp_path)})
    daemon = OrganizationalDaemon(config)
    daemon.initialize()
    daemon.observer = ObserverEngine(
        memory=daemon.memory,
        attention=FakeAttention("research", "Firefox - documentation"),
        process_provider=lambda: [{"pid": 3, "name": "firefox"}],
    )

    with (
        patch("nexus_core.organization.observer.psutil.cpu_percent", return_value=8),
        patch(
            "nexus_core.organization.observer.psutil.virtual_memory",
            return_value=type("VM", (), {"percent": 45})(),
        ),
        patch(
            "nexus_core.organization.observer.psutil.disk_usage",
            return_value=type("DU", (), {"percent": 55})(),
        ),
    ):
        result = daemon.tick_agents_once()

    assert len(result) == 9
    assert daemon.blackboard.snapshot()["mode"] == "RESEARCH"
    assert daemon.memory.counts()["observations"] >= 1
    assert daemon.memory.counts()["agent_ticks"] >= 9
