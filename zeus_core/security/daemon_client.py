"""
ZEUS DaemonClient — Abstração de comunicação com o RootDaemon.

Usado por todos os módulos que precisam executar comandos no sistema.
Comunica via Unix socket com o RootDaemon.
"""

from __future__ import annotations

import asyncio
import json
import os


def _get_socket_path() -> str:
    return os.getenv("ZEUS_DAEMON_SOCKET", "/tmp/zeus/daemon.sock")


class DaemonClient:
    """Cliente async para comunicação com o RootDaemon via Unix socket."""

    def __init__(self, socket_path: str | None = None):
        self.socket_path = socket_path or _get_socket_path()

    async def _send(self, payload: dict) -> dict:
        """Envia payload JSON e recebe resposta do daemon."""
        if not os.path.exists(self.socket_path):
            return {
                "status": "error",
                "message": f"RootDaemon não está rodando. Socket não encontrado: {self.socket_path}",
            }

        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            data = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
            writer.write(data)
            await writer.drain()

            response_data = await asyncio.wait_for(reader.readline(), timeout=90.0)
            writer.close()
            await writer.wait_closed()

            if not response_data:
                return {"status": "error", "message": "Resposta vazia do daemon."}

            return json.loads(response_data.decode())

        except asyncio.TimeoutError:
            return {
                "status": "error",
                "message": "Timeout ao aguardar resposta do daemon (90s).",
            }
        except ConnectionRefusedError:
            return {"status": "error", "message": "Conexão recusada pelo daemon."}
        except Exception as e:
            return {
                "status": "error",
                "message": f"Erro de comunicação com daemon: {e}",
            }

    # --- High-level API ---

    async def execute(
        self,
        command: str,
        reason: str = "",
        *,
        caller: str = "unknown",
        risk_accepted: bool = False,
        backup_paths: list[str] | None = None,
        rollback_plan: str = "",
    ) -> dict:
        """Executa um comando via RootDaemon."""
        return await self._send(
            {
                "action": "execute",
                "command": command,
                "reason": reason,
                "context": {
                    "caller": caller,
                    "risk_accepted": risk_accepted,
                    "backup_paths": backup_paths or [],
                    "rollback_plan": rollback_plan,
                },
            }
        )

    async def backup(self, paths: list[str]) -> dict:
        """Cria backup de arquivos."""
        return await self._send({"action": "backup", "paths": paths})

    async def rollback(self, backup_id: str) -> dict:
        """Restaura um backup."""
        return await self._send({"action": "rollback", "backup_id": backup_id})

    async def list_backups(self) -> dict:
        """Lista backups disponíveis."""
        return await self._send({"action": "list_backups"})

    async def audit_tail(self, n: int = 50) -> dict:
        """Retorna últimas entradas de auditoria."""
        return await self._send({"action": "audit_tail", "n": n})

    async def execute_batch(
        self, commands: list, reason: str = "", caller: str = "unknown"
    ) -> dict:
        """Executa múltiplos comandos em sequência."""
        return await self._send(
            {
                "action": "batch",
                "commands": commands,
                "reason": reason,
                "context": {"caller": caller},
            }
        )

    async def service_control(self, service: str, action: str) -> dict:
        """Reinicia, para ou inicia serviços do ZEUS."""
        return await self._send(
            {"action": "service_control", "service": service, "service_action": action}
        )

    async def pending_approvals(self) -> dict:
        """Retorna aprovações pendentes."""
        return await self._send({"action": "pending_approvals"})

    async def resolve_approval(self, approval_id: str, allowed: bool) -> dict:
        """Resolve uma aprovação pendente."""
        return await self._send(
            {
                "action": "approval_resolve",
                "approval_id": approval_id,
                "allowed": allowed,
            }
        )

    def is_daemon_running(self) -> bool:
        """Verifica se o socket do daemon existe."""
        return os.path.exists(self.socket_path)


# Singleton
daemon_client = DaemonClient()
