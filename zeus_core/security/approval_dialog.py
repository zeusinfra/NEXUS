"""
ZEUS Approval Dialog — GTK4/Adwaita dialog para aprovação de comandos de alto risco.

Mostra:
  - Comando/Ação
  - Motivo
  - Risco (badge colorido)
  - Arquivos afetados
  - Backup status
  - Rollback plan
  - Botões Allow / Deny

Auto-fecha em 60s com Deny por padrão (timeout safety).
"""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from typing import Callable, Optional

import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, GLib, Gio, Gtk, Adw

Adw.init()

APP_ID = "local.zeus.ApprovalDialog"
TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# Risk badge colors
# ---------------------------------------------------------------------------

RISK_COLORS = {
    "READ_ONLY": "#4ade80",
    "LOW_RISK": "#60a5fa",
    "MEDIUM_RISK": "#fbbf24",
    "HIGH_RISK": "#f97316",
    "FORBIDDEN": "#ef4444",
}

RISK_LABELS = {
    "READ_ONLY": "🟢 Somente Leitura",
    "LOW_RISK": "🔵 Baixo Risco",
    "MEDIUM_RISK": "🟡 Médio Risco",
    "HIGH_RISK": "🟠 Alto Risco",
    "FORBIDDEN": "🔴 PROIBIDO",
}


# ---------------------------------------------------------------------------
# Approval Dialog Window
# ---------------------------------------------------------------------------

class ApprovalDialog(Adw.ApplicationWindow):
    """Janela de aprovação para ações administrativas do ZEUS."""

    def __init__(
        self,
        app: Adw.Application,
        *,
        approval_id: str,
        command: str,
        reason: str,
        risk: str,
        affected_files: list[str],
        backup_id: str | None,
        rollback_plan: str,
        on_resolve: Callable[[str, bool], None],
    ):
        super().__init__(application=app)
        self._approval_id = approval_id
        self._on_resolve = on_resolve
        self._resolved = False
        self._timeout_id: int | None = None
        self._remaining = TIMEOUT_SECONDS

        self.set_title("ZEUS — Aprovação Requerida")
        self.set_default_size(560, -1)
        self.set_resizable(False)
        self.add_css_class("approval-window")

        self._install_css()
        self._build_ui(
            command=command,
            reason=reason,
            risk=risk,
            affected_files=affected_files,
            backup_id=backup_id,
            rollback_plan=rollback_plan,
        )

        # Auto-deny timeout
        self._timeout_id = GLib.timeout_add_seconds(1, self._tick_timeout)

    def _install_css(self) -> None:
        css = """
        @define-color approval_bg #0c0c10;
        @define-color card_bg rgba(18, 18, 24, 0.95);
        @define-color text_primary #e8e8ec;
        @define-color text_secondary #888890;
        @define-color accent_green #00ff88;
        @define-color accent_red #ff4455;
        @define-color border_subtle rgba(255, 255, 255, 0.06);

        .approval-window {
            background-color: @approval_bg;
        }
        .approval-card {
            background-color: @card_bg;
            border: 1px solid @border_subtle;
            border-radius: 12px;
            padding: 20px;
        }
        .approval-title {
            font-weight: 900;
            font-size: 1.1rem;
            color: #fbbf24;
            letter-spacing: 1px;
        }
        .approval-section {
            font-weight: 800;
            font-size: 0.7rem;
            letter-spacing: 1.5px;
            color: @text_secondary;
            margin-top: 12px;
        }
        .approval-command {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 0.85rem;
            color: #f8e6b0;
            background-color: rgba(0, 0, 0, 0.3);
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid rgba(255, 209, 102, 0.15);
        }
        .approval-value {
            font-size: 0.85rem;
            color: @text_primary;
        }
        .approval-file {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: @text_secondary;
            padding: 2px 0;
        }
        .risk-badge {
            font-weight: 800;
            font-size: 0.8rem;
            padding: 4px 12px;
            border-radius: 6px;
        }
        .btn-allow {
            background: @accent_green;
            color: #000;
            font-weight: 800;
            border-radius: 8px;
            padding: 10px 24px;
            font-size: 0.9rem;
        }
        .btn-allow:hover {
            background: #00e07a;
        }
        .btn-deny {
            background: @accent_red;
            color: #fff;
            font-weight: 800;
            border-radius: 8px;
            padding: 10px 24px;
            font-size: 0.9rem;
        }
        .btn-deny:hover {
            background: #e03344;
        }
        .timeout-label {
            font-size: 0.75rem;
            color: @text_secondary;
            font-family: 'JetBrains Mono', monospace;
        }
        .backup-status {
            font-size: 0.78rem;
            color: #4ade80;
            font-weight: 600;
        }
        .no-backup {
            color: @text_secondary;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(
        self,
        command: str,
        reason: str,
        risk: str,
        affected_files: list[str],
        backup_id: str | None,
        rollback_plan: str,
    ) -> None:
        # Header
        header = Adw.HeaderBar()
        title = Adw.WindowTitle(title="⚠ Aprovação Requerida", subtitle="ZEUS RootDaemon")
        header.set_title_widget(title)

        # Content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.append(header)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("approval-card")
        card.set_margin_start(20)
        card.set_margin_end(20)
        card.set_margin_top(12)
        card.set_margin_bottom(20)

        # Title row
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_label = Gtk.Label(label="ZEUS PRECISA DE APROVAÇÃO")
        title_label.add_css_class("approval-title")
        title_label.set_halign(Gtk.Align.START)
        title_row.append(title_label)

        # Risk badge
        risk_label = Gtk.Label(label=RISK_LABELS.get(risk, risk))
        risk_label.add_css_class("risk-badge")
        risk_color = RISK_COLORS.get(risk, "#888")
        badge_css = Gtk.CssProvider()
        badge_css.load_from_string(
            f".risk-badge {{ color: {risk_color}; border: 1px solid {risk_color}; }}"
        )
        risk_label.get_style_context().add_provider(badge_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        title_row.append(risk_label)
        card.append(title_row)

        # COMANDO
        cmd_section = Gtk.Label(label="COMANDO")
        cmd_section.add_css_class("approval-section")
        cmd_section.set_halign(Gtk.Align.START)
        card.append(cmd_section)

        cmd_label = Gtk.Label(label=command)
        cmd_label.add_css_class("approval-command")
        cmd_label.set_halign(Gtk.Align.FILL)
        cmd_label.set_wrap(True)
        cmd_label.set_selectable(True)
        card.append(cmd_label)

        # MOTIVO
        reason_section = Gtk.Label(label="MOTIVO")
        reason_section.add_css_class("approval-section")
        reason_section.set_halign(Gtk.Align.START)
        card.append(reason_section)

        reason_label = Gtk.Label(label=reason or "Nenhum motivo informado")
        reason_label.add_css_class("approval-value")
        reason_label.set_halign(Gtk.Align.START)
        reason_label.set_wrap(True)
        card.append(reason_label)

        # ARQUIVOS AFETADOS
        if affected_files:
            files_section = Gtk.Label(label="ARQUIVOS AFETADOS")
            files_section.add_css_class("approval-section")
            files_section.set_halign(Gtk.Align.START)
            card.append(files_section)

            for f in affected_files[:10]:  # Limit display
                file_label = Gtk.Label(label=f"  📄 {f}")
                file_label.add_css_class("approval-file")
                file_label.set_halign(Gtk.Align.START)
                card.append(file_label)
            if len(affected_files) > 10:
                more = Gtk.Label(label=f"  ... e mais {len(affected_files) - 10} arquivos")
                more.add_css_class("approval-file")
                card.append(more)

        # BACKUP
        backup_section = Gtk.Label(label="BACKUP")
        backup_section.add_css_class("approval-section")
        backup_section.set_halign(Gtk.Align.START)
        card.append(backup_section)

        if backup_id:
            backup_label = Gtk.Label(label=f"✓ Backup criado: {backup_id}")
            backup_label.add_css_class("backup-status")
        else:
            backup_label = Gtk.Label(label="— Sem backup necessário")
            backup_label.add_css_class("no-backup")
        backup_label.set_halign(Gtk.Align.START)
        card.append(backup_label)

        # ROLLBACK
        if rollback_plan:
            rollback_section = Gtk.Label(label="PLANO DE ROLLBACK")
            rollback_section.add_css_class("approval-section")
            rollback_section.set_halign(Gtk.Align.START)
            card.append(rollback_section)

            rollback_label = Gtk.Label(label=rollback_plan)
            rollback_label.add_css_class("approval-value")
            rollback_label.set_halign(Gtk.Align.START)
            rollback_label.set_wrap(True)
            card.append(rollback_label)

        content.append(card)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_bottom(20)

        deny_btn = Gtk.Button(label="✕  DENY")
        deny_btn.add_css_class("btn-deny")
        deny_btn.connect("clicked", lambda _: self._resolve(False))
        button_box.append(deny_btn)

        allow_btn = Gtk.Button(label="✓  ALLOW")
        allow_btn.add_css_class("btn-allow")
        allow_btn.connect("clicked", lambda _: self._resolve(True))
        button_box.append(allow_btn)

        content.append(button_box)

        # Timeout label
        self._timeout_label = Gtk.Label(label=f"Auto-deny em {self._remaining}s")
        self._timeout_label.add_css_class("timeout-label")
        self._timeout_label.set_halign(Gtk.Align.CENTER)
        self._timeout_label.set_margin_bottom(16)
        content.append(self._timeout_label)

        self.set_content(content)

    def _tick_timeout(self) -> bool:
        if self._resolved:
            return False
        self._remaining -= 1
        if self._remaining <= 0:
            self._resolve(False)
            return False
        self._timeout_label.set_label(f"Auto-deny em {self._remaining}s")
        return True

    def _resolve(self, allowed: bool) -> None:
        if self._resolved:
            return
        self._resolved = True
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
        self._on_resolve(self._approval_id, allowed)
        self.close()


# ---------------------------------------------------------------------------
# Standalone approval app (pode ser chamado como processo separado)
# ---------------------------------------------------------------------------

class ApprovalApp(Adw.Application):
    """Aplicação GTK4 standalone para mostrar approval dialog."""

    def __init__(self, approval_data: dict, on_resolve: Callable[[str, bool], None]):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._data = approval_data
        self._on_resolve = on_resolve
        self._result: tuple[str, bool] | None = None

    def do_activate(self) -> None:
        dialog = ApprovalDialog(
            self,
            approval_id=self._data.get("id", "unknown"),
            command=self._data.get("command", "???"),
            reason=self._data.get("reason", ""),
            risk=self._data.get("risk", "HIGH_RISK"),
            affected_files=self._data.get("affected_files", []),
            backup_id=self._data.get("backup_id"),
            rollback_plan=self._data.get("rollback_plan", ""),
            on_resolve=self._handle_resolve,
        )
        dialog.present()

    def _handle_resolve(self, approval_id: str, allowed: bool) -> None:
        self._result = (approval_id, allowed)
        self._on_resolve(approval_id, allowed)
        GLib.timeout_add(300, self.quit)


def show_approval_dialog(approval_data: dict) -> tuple[str, bool]:
    """
    Mostra o dialog de aprovação e retorna (approval_id, allowed).
    BLOCKING — roda o GTK main loop.
    """
    result = {"id": approval_data.get("id", ""), "allowed": False}

    def on_resolve(aid: str, allowed: bool):
        result["id"] = aid
        result["allowed"] = allowed

    app = ApprovalApp(approval_data, on_resolve)
    app.run()
    return result["id"], result["allowed"]


# ---------------------------------------------------------------------------
# CLI entrypoint (para uso por outros processos)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Usage: python3 -m zeus_core.security.approval_dialog '{"id":"abc","command":"apt upgrade",...}'
    if len(sys.argv) > 1:
        data = json.loads(sys.argv[1])
    else:
        data = {
            "id": "test_001",
            "command": "apt upgrade -y",
            "reason": "Atualizar pacotes do sistema para corrigir vulnerabilidades",
            "risk": "HIGH_RISK",
            "affected_files": ["/etc/apt/sources.list", "/var/lib/dpkg/status"],
            "backup_id": "20260509_204500_a1b2c3",
            "rollback_plan": "Restaurar backup 20260509_204500_a1b2c3",
        }

    aid, allowed = show_approval_dialog(data)
    # Output result as JSON for caller
    print(json.dumps({"approval_id": aid, "allowed": allowed}))
    sys.exit(0 if allowed else 1)
