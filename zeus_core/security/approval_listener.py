"""
ZEUS Approval Listener — Monitora aprovações pendentes do RootDaemon e mostra GTK dialog.

Roda como thread/task dentro do zeus-gtk-chat ou como processo standalone.
Faz polling no daemon a cada 2s por aprovações pendentes.
Quando encontra uma, mostra o ApprovalDialog e envia a resolução de volta ao daemon.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from typing import Optional

# Importação condicional do GTK (pode rodar sem GUI em modo headless)
_GTK_AVAILABLE = False
try:
    import gi
    gi.require_version("Gtk", "4.0")
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    pass


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class ApprovalListener:
    """Escuta por aprovações pendentes e mostra dialogs GTK."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._running = False
        self._processing: set[str] = set()  # IDs being processed
        self._daemon_client = None

    def _get_client(self):
        if self._daemon_client is None:
            from zeus_core.security.daemon_client import DaemonClient
            self._daemon_client = DaemonClient()
        return self._daemon_client

    async def poll_once(self) -> list[dict]:
        """Verifica aprovações pendentes no daemon."""
        client = self._get_client()
        if not client.is_daemon_running():
            return []

        result = await client.pending_approvals()
        if result.get("status") == "success":
            return result.get("pending", [])
        return []

    async def resolve(self, approval_id: str, allowed: bool) -> dict:
        """Envia resolução de volta ao daemon."""
        client = self._get_client()
        return await client.resolve_approval(approval_id, allowed)

    def show_dialog_subprocess(self, approval_data: dict) -> bool:
        """
        Mostra o dialog de aprovação como subprocesso.
        Retorna True se aprovado, False se negado.
        """
        try:
            data_json = json.dumps(approval_data)
            result = subprocess.run(
                [
                    sys.executable, "-m",
                    "zeus_core.security.approval_dialog",
                    data_json,
                ],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=ROOT_DIR,
            )
            if result.returncode == 0:
                return True
            return False
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            print(f"[ApprovalListener] Erro ao mostrar dialog: {e}")
            return False

    async def _process_approval(self, approval: dict) -> None:
        """Processa uma aprovação pendente."""
        aid = approval.get("id", "")
        if aid in self._processing:
            return

        self._processing.add(aid)
        try:
            # Mostrar dialog em thread separada (GTK precisa da main thread)
            loop = asyncio.get_event_loop()
            allowed = await loop.run_in_executor(
                None, self.show_dialog_subprocess, approval
            )

            # Enviar resolução
            result = await self.resolve(aid, allowed)
            status = "ALLOWED" if allowed else "DENIED"
            print(f"[ApprovalListener] {aid}: {status} -> {result.get('status', '?')}")
        finally:
            self._processing.discard(aid)

    async def run(self) -> None:
        """Loop principal de polling."""
        self._running = True
        print(f"[ApprovalListener] ✓ Iniciado (polling a cada {self.poll_interval}s)")

        while self._running:
            try:
                pending = await self.poll_once()
                for approval in pending:
                    aid = approval.get("id", "")
                    if aid not in self._processing:
                        asyncio.create_task(self._process_approval(approval))
            except Exception as e:
                print(f"[ApprovalListener] Erro no polling: {e}")

            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False


# Singleton
approval_listener = ApprovalListener()


# ---------------------------------------------------------------------------
# GLib integration (para usar dentro do zeus-gtk-chat)
# ---------------------------------------------------------------------------

def start_approval_listener_glib(on_pending_callback=None):
    """
    Inicia o listener de aprovações integrado ao GLib main loop.
    Usado pelo zeus-gtk-chat para mostrar dialogs inline.
    
    on_pending_callback: chamado com (approval_data) quando há aprovação pendente.
                         Se None, usa subprocess para mostrar dialog.
    """
    if not _GTK_AVAILABLE:
        print("[ApprovalListener] GTK não disponível. Listener desabilitado.")
        return

    from gi.repository import GLib

    listener = ApprovalListener()
    _seen: set[str] = set()

    def _check():
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            pending = loop.run_until_complete(listener.poll_once())
            loop.close()

            for approval in pending:
                aid = approval.get("id", "")
                if aid not in _seen:
                    _seen.add(aid)
                    if on_pending_callback:
                        GLib.idle_add(on_pending_callback, approval)
                    else:
                        # Usar subprocess
                        threading.Thread(
                            target=_subprocess_resolve,
                            args=(listener, approval),
                            daemon=True,
                        ).start()
        except Exception as e:
            print(f"[ApprovalListener][GLib] Erro: {e}")
        return True  # Continua polling

    def _subprocess_resolve(lst: ApprovalListener, data: dict):
        allowed = lst.show_dialog_subprocess(data)
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(lst.resolve(data.get("id", ""), allowed))
            loop.close()
        except Exception as e:
            print(f"[ApprovalListener] Resolve error: {e}")

    GLib.timeout_add(int(listener.poll_interval * 1000), _check)
    print("[ApprovalListener][GLib] ✓ Integrado ao main loop GTK")


# ---------------------------------------------------------------------------
# Standalone entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    listener = ApprovalListener()
    asyncio.run(listener.run())
