import pytest
from unittest.mock import AsyncMock, patch

from zeus_core.security.root_daemon import RootDaemon

@pytest.fixture
def root_daemon_instance():
    return RootDaemon()

@pytest.mark.asyncio
async def test_service_name_accepts_common_systemd_units(root_daemon_instance, monkeypatch):
    calls = []
    # Mocking the synchronous _run_command instead of asyncio.to_thread
    async def mock_to_thread(func, arg):
        calls.append(arg)
        return {"status": "success"}
    monkeypatch.setattr("asyncio.to_thread", mock_to_thread)

    result = await root_daemon_instance.handle_service_control({"service": "zeus_core", "service_action": "status"})

    assert result["status"] == "success"
    assert calls == ["systemctl --user status zeus_core"]


@pytest.mark.asyncio
async def test_service_name_rejects_shell_payload(root_daemon_instance, monkeypatch):
    async def mock_to_thread(func, arg):
        pytest.fail("should not execute")
    monkeypatch.setattr("asyncio.to_thread", mock_to_thread)

    result = await root_daemon_instance.handle_service_control({"service": "zeus;reboot", "service_action": "status"})

    assert result["status"] == "blocked"
    assert "não permitida" in result["message"]


@pytest.mark.asyncio
async def test_execute_safe_command_rejects_prefix_collision(root_daemon_instance, monkeypatch):
    async def mock_to_thread(func, arg):
        pytest.fail("should not execute")
    monkeypatch.setattr("asyncio.to_thread", mock_to_thread)

    # In the new implementation, "dfnotreal -h" might be classified as HIGH_RISK, 
    # requiring approval, so it shouldn't execute directly.
    result = await root_daemon_instance.handle_execute({"command": "dfnotreal -h"})

    assert result["status"] in ("error", "blocked", "requires_approval")


@pytest.mark.asyncio
async def test_execute_safe_command_allows_tokenized_read_only_command(root_daemon_instance, monkeypatch):
    calls = []
    async def mock_to_thread(func, arg):
        calls.append(arg)
        return {"status": "success"}
    monkeypatch.setattr("asyncio.to_thread", mock_to_thread)

    # "systemctl status ..." is a read-only command according to classify_risk
    result = await root_daemon_instance.handle_execute({"command": "systemctl status zeus-core.service"})

    assert result["status"] == "success"
    assert calls == ["systemctl status zeus-core.service"]
