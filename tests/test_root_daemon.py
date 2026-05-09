import pytest

from zeus_core.security import root_daemon


@pytest.mark.asyncio
async def test_service_name_accepts_common_systemd_units(monkeypatch):
    calls = []
    monkeypatch.setattr(root_daemon, "_run_shell", lambda args: calls.append(args) or {"status": "success"})

    result = await root_daemon.get_service_status("zeus-core.service")

    assert result["status"] == "success"
    assert calls == [["systemctl", "status", "zeus-core.service"]]


@pytest.mark.asyncio
async def test_service_name_rejects_shell_payload(monkeypatch):
    monkeypatch.setattr(root_daemon, "_run_shell", lambda args: pytest.fail("should not execute"))

    result = await root_daemon.get_service_status("zeus;reboot")

    assert result["status"] == "error"
    assert "Invalid service name" in result["message"]


@pytest.mark.asyncio
async def test_execute_safe_command_rejects_prefix_collision(monkeypatch):
    monkeypatch.setattr(root_daemon, "_run_shell", lambda args: pytest.fail("should not execute"))

    result = await root_daemon.execute_safe_command("dfnotreal -h")

    assert result["status"] == "error"
    assert "rejected" in result["message"]


@pytest.mark.asyncio
async def test_execute_safe_command_allows_tokenized_read_only_command(monkeypatch):
    calls = []
    monkeypatch.setattr(root_daemon, "_run_shell", lambda args: calls.append(args) or {"status": "success"})

    result = await root_daemon.execute_safe_command("systemctl status zeus-core.service")

    assert result["status"] == "success"
    assert calls == [["systemctl", "status", "zeus-core.service"]]
