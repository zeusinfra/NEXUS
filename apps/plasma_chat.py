#!/usr/bin/env python3
from __future__ import annotations

import json
import base64
import atexit
import faulthandler
import os
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from PySide6.QtCore import Qt, QThread, QTimer, Signal
    from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QScrollArea,
        QSizePolicy,
        QSystemTrayIcon,
        QTableWidget,
        QTableWidgetItem,
        QTextBrowser,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    try:
        from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal as Signal
        from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut
        from PyQt6.QtWidgets import (
            QApplication,
            QFrame,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPushButton,
            QProgressBar,
            QScrollArea,
            QSizePolicy,
            QSystemTrayIcon,
            QTableWidget,
            QTableWidgetItem,
            QTextBrowser,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        print(
            "Erro: instale PySide6 ou PyQt6 para usar a GUI Plasma.\n"
            "Debian/Ubuntu/KDE neon: sudo apt install python3-pyqt6\n"
            "Venv: python -m pip install PySide6",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


BACKEND = os.getenv("NEXUS_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")
CLIENT_ID = os.getenv("NEXUS_PLASMA_CLIENT_ID", "nexus_plasma_gui").strip()
SESSION_ID = os.getenv("NEXUS_PLASMA_SESSION_ID") or datetime.now().strftime(
    "plasma-%Y%m%d-%H%M%S"
)
ICON_PATH = ROOT_DIR / "assets" / "icons" / "nexus-plasma-chat.svg"
VISIBLE_WORKERS = {
    "chat": "Processando pedido...",
    "tts": "Gerando voz...",
    "voice_start": "Armando escuta local...",
}
NON_OVERLAPPING_WORKERS = {"health", "status", "events"}


def _request_json(
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    timeout: float = 30.0,
) -> dict:
    data = None
    headers = {
        "Accept": "application/json",
        "X-NEXUS-Client-ID": CLIENT_ID,
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{BACKEND}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


class ApiWorker(QThread):
    finished = Signal(str, dict)
    failed = Signal(str, str)

    def __init__(
        self,
        name: str,
        method: str,
        path: str,
        payload: dict | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__()
        self.name = name
        self.method = method
        self.path = path
        self.payload = payload
        self.timeout = timeout

    def run(self) -> None:
        try:
            self.finished.emit(
                self.name,
                _request_json(
                    self.method,
                    self.path,
                    payload=self.payload,
                    timeout=self.timeout,
                ),
            )
        except Exception as exc:
            self.failed.emit(self.name, str(exc))


class PlasmaChatWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NEXUS Plasma")
        self.setWindowIcon(_app_icon())
        self.setMinimumSize(980, 680)
        self.resize(1180, 760)

        self._workers: list[ApiWorker] = []
        self._active_worker_names: set[str] = set()
        self._visible_workers: dict[ApiWorker, str] = {}
        self._activity_items: list[str] = []
        self._seen_event_keys: set[str] = set()
        self._sending = False
        self._allow_exit = False
        self._last_health: dict = {}
        self._voice_enabled = True
        self._last_speech_text = ""

        self._build_ui()
        self._build_tray()
        self._install_shortcuts()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(3000)

        self.events_timer = QTimer(self)
        self.events_timer.timeout.connect(self.poll_events)
        self.events_timer.start(900)

        self.refresh_status()
        self.poll_events()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(300)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 18, 20, 18)
        side_layout.setSpacing(14)

        brand_row = QHBoxLayout()
        brand_icon = QLabel()
        brand_icon.setObjectName("brandIcon")
        pixmap = _app_icon().pixmap(52, 52)
        if not pixmap.isNull():
            brand_icon.setPixmap(pixmap)
        brand_icon.setFixedSize(56, 56)
        brand_icon.setScaledContents(False)

        brand_text = QVBoxLayout()
        title = QLabel("NEXUS")
        title.setObjectName("brand")
        subtitle = QLabel("Plasma Command Surface")
        subtitle.setObjectName("subtitle")
        brand_text.addWidget(title)
        brand_text.addWidget(subtitle)
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_text, 1)
        side_layout.addLayout(brand_row)

        self.backend_label = QLabel("Backend: verificando")
        self.mode_label = QLabel("Modo: --")
        self.llm_label = QLabel("LLM: --")
        self.watcher_label = QLabel("Watcher: --")
        self.memory_label = QLabel("Memoria: --")
        self.security_label = QLabel("Autonomia: --")
        for label in (
            self.backend_label,
            self.mode_label,
            self.llm_label,
            self.watcher_label,
            self.memory_label,
            self.security_label,
        ):
            label.setObjectName("metric")
            label.setWordWrap(True)
            side_layout.addWidget(label)

        self.status_button = QPushButton("Recarregar status")
        self.status_button.clicked.connect(self.refresh_status)
        side_layout.addWidget(self.status_button)

        self.ensure_button = QPushButton("Garantir backend")
        self.ensure_button.clicked.connect(self.ensure_backend)
        side_layout.addWidget(self.ensure_button)

        self.listen_button = QPushButton("Escutar 10s")
        self.listen_button.clicked.connect(self.start_voice_listening)
        side_layout.addWidget(self.listen_button)

        self.open_web_button = QPushButton("Abrir console web")
        self.open_web_button.clicked.connect(self.open_web_console)
        side_layout.addWidget(self.open_web_button)

        events_title = QLabel("Eventos")
        events_title.setObjectName("sectionTitle")
        side_layout.addWidget(events_title)

        self.events_table = QTableWidget(0, 2)
        self.events_table.setHorizontalHeaderLabels(["Tipo", "Detalhe"])
        self.events_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.events_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.setShowGrid(False)
        self.events_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        side_layout.addWidget(self.events_table, 1)

        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 18, 22, 18)
        content_layout.setSpacing(12)

        top_row = QHBoxLayout()
        heading = QLabel("Operador NEXUS")
        heading.setObjectName("heading")
        self.connection_badge = QLabel("OFFLINE")
        self.connection_badge.setObjectName("badgeOffline")
        top_row.addWidget(heading)
        top_row.addStretch(1)
        top_row.addWidget(self.connection_badge)
        content_layout.addLayout(top_row)

        self.chat = QTextBrowser()
        self.chat.setObjectName("chat")
        self.chat.setOpenExternalLinks(True)
        content_layout.addWidget(self.chat, 1)

        self.activity_bar = QProgressBar()
        self.activity_bar.setObjectName("activityBar")
        self.activity_bar.setRange(0, 1)
        self.activity_bar.setValue(0)
        self.activity_bar.setTextVisible(False)
        self.activity_bar.setFixedHeight(7)
        content_layout.addWidget(self.activity_bar)

        self.progress_label = QLabel("Pronto.")
        self.progress_label.setObjectName("progress")
        content_layout.addWidget(self.progress_label)

        self.activity_log = QTextBrowser()
        self.activity_log.setObjectName("activityLog")
        self.activity_log.setFixedHeight(118)
        self.activity_log.setOpenExternalLinks(False)
        content_layout.addWidget(self.activity_log)

        composer = QFrame()
        composer.setObjectName("composer")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(12, 12, 12, 12)
        composer_layout.setSpacing(10)

        self.input = QTextEdit()
        self.input.setPlaceholderText("Digite sua mensagem para o NEXUS")
        self.input.setFixedHeight(96)
        composer_layout.addWidget(self.input)

        controls = QHBoxLayout()
        self.backend_input = QLineEdit(BACKEND)
        self.backend_input.setPlaceholderText("Backend URL")
        self.backend_input.editingFinished.connect(self._backend_changed)
        controls.addWidget(self.backend_input, 1)

        self.send_button = QPushButton("Enviar")
        self.send_button.setDefault(True)
        self.send_button.clicked.connect(self.send_message)
        controls.addWidget(self.send_button)

        self.voice_button = QPushButton("Voz: ligada")
        self.voice_button.setCheckable(True)
        self.voice_button.setChecked(True)
        self.voice_button.clicked.connect(self.toggle_voice)
        controls.addWidget(self.voice_button)

        self.speak_button = QPushButton("Falar resposta")
        self.speak_button.clicked.connect(self.speak_last_response)
        controls.addWidget(self.speak_button)
        composer_layout.addLayout(controls)

        content_layout.addWidget(composer)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self._apply_styles()

        self.add_message(
            "system",
            "NEXUS Plasma pronto. Envie uma tarefa; cada etapa aparece em Atividade.",
        )
        self._add_activity("Interface iniciada. Aguardando pedido.")

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(_app_icon(), self)
        self.tray.setToolTip("NEXUS Plasma")
        menu = QMenu()
        show_action = QAction("Mostrar", self)
        show_action.triggered.connect(self.show_normal)
        menu.addAction(show_action)
        status_action = QAction("Recarregar status", self)
        status_action.triggered.connect(self.refresh_status)
        menu.addAction(status_action)
        quit_action = QAction("Sair", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _install_shortcuts(self) -> None:
        send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        send_shortcut.activated.connect(self.send_message)
        send_shortcut2 = QShortcut(QKeySequence("Ctrl+Enter"), self)
        send_shortcut2.activated.connect(self.send_message)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, #content {
                background: #151719;
                color: #e7eaee;
                font-size: 14px;
            }
            #sidebar {
                background: #101214;
                border-right: 1px solid #2a3035;
            }
            #brand {
                color: #77e0d4;
                font-size: 28px;
                font-weight: 800;
                letter-spacing: 0;
            }
            #brandIcon {
                background: #151b1f;
                border: 1px solid #2d3c42;
                border-radius: 8px;
                padding: 2px;
            }
            #subtitle, #progress {
                color: #9aa5ad;
            }
            #heading {
                font-size: 22px;
                font-weight: 700;
            }
            #sectionTitle {
                color: #c6d1d8;
                font-weight: 700;
                margin-top: 10px;
            }
            #metric {
                color: #d8dee4;
                padding: 7px 0;
                border-bottom: 1px solid #242a2f;
            }
            #badgeOnline, #badgeOffline {
                border-radius: 4px;
                padding: 6px 10px;
                font-weight: 700;
            }
            #badgeOnline {
                background: #123b33;
                color: #84f0cf;
            }
            #badgeOffline {
                background: #461c21;
                color: #ffb0b8;
            }
            #chat {
                background: #0f1113;
                color: #e7eaee;
                border: 1px solid #2a3035;
                border-radius: 6px;
                padding: 12px;
            }
            #activityLog {
                background: #111417;
                color: #d8dee4;
                border: 1px solid #283139;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            #activityBar {
                border: 0;
                border-radius: 3px;
                background: #20262b;
            }
            #activityBar::chunk {
                border-radius: 3px;
                background: #77e0d4;
            }
            #composer {
                background: #101214;
                border: 1px solid #2a3035;
                border-radius: 6px;
            }
            QTextEdit, QLineEdit {
                background: #171b1f;
                color: #eef2f5;
                border: 1px solid #333b42;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #27645d;
            }
            QPushButton {
                background: #23333a;
                color: #f2f6f8;
                border: 1px solid #3a4a52;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2d424b;
            }
            QPushButton:disabled {
                color: #747d85;
                background: #1b2024;
            }
            QPushButton:checked {
                background: #17443d;
                border-color: #2b7f72;
                color: #a6fff0;
            }
            QTableWidget {
                background: #101214;
                color: #d8dee4;
                border: 1px solid #2a3035;
                border-radius: 4px;
            }
            QHeaderView::section {
                background: #171b1f;
                color: #c6d1d8;
                border: 0;
                padding: 6px;
            }
            """
        )

    def _backend_changed(self) -> None:
        global BACKEND
        value = self.backend_input.text().strip().rstrip("/")
        if value:
            BACKEND = value
            self.refresh_status()

    def show_normal(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_normal()

    def quit_app(self) -> None:
        self._allow_exit = True
        app = QApplication.instance()
        if app:
            app.quit()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._allow_exit:
            super().closeEvent(event)
            return
        if self.tray and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "NEXUS Plasma",
                "Continuo ativo na bandeja do Plasma.",
                QSystemTrayIcon.MessageIcon.Information,
                2200,
            )
            return
        event.ignore()
        self.showMinimized()
        self._add_activity("Janela minimizada. Use Sair no menu da bandeja para encerrar.")

    def add_message(self, role: str, text: str) -> None:
        safe = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        palette = {
            "user": ("Voce", "#77e0d4"),
            "assistant": ("NEXUS", "#f0d98a"),
            "system": ("Sistema", "#9aa5ad"),
            "error": ("Erro", "#ff9aa2"),
        }
        label, color = palette.get(role, ("Evento", "#c6d1d8"))
        self.chat.append(
            f'<p style="margin:10px 0;"><span style="color:{color};'
            f'font-weight:700;">{label}</span><br>{safe}</p>'
        )
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def _add_activity(self, text: str, *, kind: str = "info") -> None:
        safe = (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        color = {
            "ok": "#84f0cf",
            "warn": "#f0d98a",
            "error": "#ff9aa2",
            "work": "#77e0d4",
        }.get(kind, "#c6d1d8")
        stamp = datetime.now().strftime("%H:%M:%S")
        self._activity_items.insert(
            0,
            f'<p style="margin:3px 0;"><span style="color:#79848c;">{stamp}</span> '
            f'<span style="color:{color};">{safe}</span></p>',
        )
        self._activity_items = self._activity_items[:40]
        self.activity_log.setHtml("".join(self._activity_items))

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        if busy:
            self.activity_bar.setRange(0, 0)
            self.progress_label.setText(text or "Trabalhando...")
            return
        self.activity_bar.setRange(0, 1)
        self.activity_bar.setValue(0)
        if text:
            self.progress_label.setText(text)

    def _start_worker(
        self,
        name: str,
        method: str,
        path: str,
        payload: dict | None = None,
        timeout: float = 30.0,
    ) -> None:
        if name in NON_OVERLAPPING_WORKERS and name in self._active_worker_names:
            return
        worker = ApiWorker(name, method, path, payload, timeout)
        worker.finished.connect(self._worker_finished)
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        worker.failed.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        self._active_worker_names.add(name)
        if name in VISIBLE_WORKERS:
            self._visible_workers[worker] = name
            self._set_busy(True, VISIBLE_WORKERS[name])
            self._add_activity(VISIBLE_WORKERS[name], kind="work")
        worker.start()

    def _cleanup_worker(self, worker: ApiWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        self._active_worker_names.discard(worker.name)
        self._visible_workers.pop(worker, None)
        if not self._visible_workers and not self._sending:
            self._set_busy(False)
        worker.deleteLater()

    def refresh_status(self) -> None:
        self._start_worker("health", "GET", "/api/health", timeout=5)
        self._start_worker("status", "GET", "/status", timeout=5)

    def poll_events(self) -> None:
        query = urllib.parse.urlencode({"client_id": CLIENT_ID})
        self._start_worker("events", "GET", f"/api/events/drain?{query}", timeout=4)

    def send_message(self) -> None:
        if self._sending:
            return
        message = self.input.toPlainText().strip()
        if not message:
            return
        self.input.clear()
        self.add_message("user", message)
        client_msg_id = str(uuid.uuid4())
        self._seen_event_keys.add(f"CHAT_USER:{client_msg_id}")
        self._sending = True
        self.send_button.setEnabled(False)
        self._set_busy(True, "Processando pedido...")
        self._add_activity("Pedido enviado ao agente.", kind="work")
        payload = {
            "message": message,
            "client_msg_id": client_msg_id,
            "source": "plasma_gui",
            "client_id": CLIENT_ID,
            "session_id": SESSION_ID,
            "voice_response": self._voice_enabled,
        }
        self._start_worker("chat", "POST", "/api/applet/chat", payload, timeout=120)

    def toggle_voice(self) -> None:
        self._voice_enabled = self.voice_button.isChecked()
        self.voice_button.setText(
            "Voz: ligada" if self._voice_enabled else "Voz: mutada"
        )
        self.progress_label.setText(
            "Voz ativada para respostas."
            if self._voice_enabled
            else "Voz desativada."
        )

    def speak_last_response(self) -> None:
        if not self._last_speech_text:
            self.progress_label.setText("Ainda nao ha resposta para falar.")
            return
        self._start_worker(
            "tts",
            "POST",
            "/api/tts",
            {"text": self._last_speech_text},
            timeout=60,
        )

    def start_voice_listening(self) -> None:
        self.progress_label.setText("Armando escuta local por 10 segundos...")
        self._add_activity("Escuta local solicitada por 10 segundos.", kind="work")
        self._start_worker(
            "voice_start",
            "POST",
            "/api/applet/voice/start",
            {"duration": 10},
            timeout=10,
        )

    def ensure_backend(self) -> None:
        self._set_busy(True, "Garantindo backend...")
        self._add_activity("Solicitando inicialização do backend.", kind="work")
        try:
            subprocess.Popen(
                [str(ROOT_DIR / "bin" / "nexus"), "ensure-server"],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            self.add_message("error", f"Falha ao iniciar backend: {exc}")
            self._add_activity(f"Falha ao iniciar backend: {exc}", kind="error")
            self._set_busy(False, "Falha ao iniciar backend.")
            return
        QTimer.singleShot(1800, self._finish_backend_ensure)

    def _finish_backend_ensure(self) -> None:
        self._set_busy(False, "Backend solicitado. Recarregando status.")
        self._add_activity("Backend solicitado; verificando saude.", kind="ok")
        self.refresh_status()

    def open_web_console(self) -> None:
        try:
            subprocess.Popen(["xdg-open", BACKEND], stdout=subprocess.DEVNULL)
        except Exception as exc:
            QMessageBox.warning(self, "NEXUS Plasma", str(exc))

    def _worker_finished(self, name: str, data: dict) -> None:
        if name == "health":
            self._last_health = data
            self._render_health(data)
        elif name == "status":
            self._render_status(data)
        elif name == "events":
            self._render_events(data.get("events", []))
        elif name == "chat":
            self._sending = False
            self.send_button.setEnabled(True)
            self._set_busy(False, "Resposta recebida.")
            self._add_activity("Resposta recebida.", kind="ok")
            reply = data.get("reply") or data.get("raw_reply") or "(sem resposta)"
            self._last_speech_text = str(data.get("speech_reply") or reply)
            if data.get("id"):
                self._seen_event_keys.add(f"CHAT_AI:{data.get('id')}")
            self.add_message("assistant", str(reply))
            audio = data.get("audio") or ""
            if self._voice_enabled and audio:
                self._play_audio_b64(str(audio))
            elif self._voice_enabled:
                self._start_worker(
                    "tts",
                    "POST",
                    "/api/tts",
                    {"text": self._last_speech_text},
                    timeout=60,
                )
        elif name == "tts":
            audio = data.get("audio") or ""
            if audio:
                self._play_audio_b64(str(audio))
                self._add_activity("Audio de resposta reproduzido.", kind="ok")
            else:
                self.add_message(
                    "system",
                    "TTS indisponivel. Instale edge-tts para gerar voz no backend.",
                )
        elif name == "voice_start":
            duration = data.get("duration", 10)
            self.progress_label.setText(f"Escuta armada por {duration}s.")
            self._add_activity(f"Escuta armada por {duration}s.", kind="ok")

    def _worker_failed(self, name: str, error: str) -> None:
        if name == "health":
            self.connection_badge.setText("OFFLINE")
            self.connection_badge.setObjectName("badgeOffline")
            self.connection_badge.style().unpolish(self.connection_badge)
            self.connection_badge.style().polish(self.connection_badge)
            self.backend_label.setText(f"Backend: offline ({error})")
            self._add_activity(f"Backend offline: {error}", kind="error")
            return
        if name == "events":
            return
        if name == "chat":
            self._sending = False
            self.send_button.setEnabled(True)
            self._set_busy(False, "Falha no pedido.")
            self.add_message("error", error)
            self._add_activity(f"Falha no pedido: {error}", kind="error")
            return
        if name in {"tts", "voice_start"}:
            self.add_message("error", error)
            self._add_activity(error, kind="error")
            return
        self.progress_label.setText(error)
        self._add_activity(error, kind="error")

    def _play_audio_b64(self, audio_b64: str) -> None:
        try:
            raw = base64.b64decode(audio_b64)
        except Exception as exc:
            self.add_message("error", f"Audio invalido: {exc}")
            return

        tmp = tempfile.NamedTemporaryFile(
            prefix="nexus-plasma-tts-", suffix=".mp3", delete=False
        )
        with tmp:
            tmp.write(raw)

        player = _find_audio_player()
        if not player:
            self.add_message(
                "system",
                "Instale vlc, dragon, mpv ou ffplay para tocar respostas de voz.",
            )
            return

        name = os.path.basename(player)
        if name == "ffplay":
            args = [player, "-nodisp", "-autoexit", "-loglevel", "quiet", tmp.name]
        elif name == "mpv":
            args = [player, "--no-terminal", tmp.name]
        elif name == "vlc":
            args = [player, "--intf", "dummy", "--play-and-exit", tmp.name]
        else:
            args = [player, tmp.name]
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _render_health(self, data: dict) -> None:
        self.connection_badge.setText("ONLINE")
        self.connection_badge.setObjectName("badgeOnline")
        self.connection_badge.style().unpolish(self.connection_badge)
        self.connection_badge.style().polish(self.connection_badge)
        self.backend_label.setText(f"Backend: {BACKEND}")

        llm = data.get("llm", {})
        config = data.get("config", {})
        watcher = data.get("watcher", {})
        memory = data.get("memory", {})
        capabilities = data.get("capabilities", {})
        execution = capabilities.get("execution", {})

        self.mode_label.setText(f"Modo: {config.get('mode', '--')}")
        self.llm_label.setText(
            f"LLM: {llm.get('provider', '--')} / {llm.get('model', '--')}"
        )
        self.watcher_label.setText(f"Watcher: {watcher.get('status', '--')}")
        self.memory_label.setText(f"Memoria: {memory.get('status', '--')}")
        self.security_label.setText(
            f"Autonomia: {execution.get('autonomy_level', '--')}"
        )
        if self.tray:
            self.tray.setToolTip("NEXUS Plasma: online")

    def _render_status(self, data: dict) -> None:
        cpu = data.get("cpu", [])
        ram = data.get("ram", "--")
        active = data.get("active_path", "NEXUS / IDLE")
        if isinstance(cpu, list) and cpu:
            cpu_avg = round(sum(float(v) for v in cpu) / len(cpu), 1)
            self.mode_label.setText(f"CPU: {cpu_avg}% | RAM: {ram}%")
        if not self._sending and not self._visible_workers:
            self.progress_label.setText(f"Foco: {active}")

    def _render_events(self, events: list) -> None:
        for event in events:
            event_type = str(event.get("type") or "EVENT")
            text = (
                event.get("text")
                or event.get("message")
                or event.get("command")
                or event.get("path")
                or event.get("stage")
                or event.get("status")
                or ""
            )
            key = (
                f"{event_type}:{event.get('id')}"
                if event.get("id")
                else f"{event_type}:{text}:{time.time()}"
            )
            if key in self._seen_event_keys:
                continue
            self._seen_event_keys.add(key)

            if event_type == "AGENT_PROGRESS" and text:
                self.progress_label.setText(str(text))
                kind = (
                    "ok"
                    if event.get("stage") in {"completed", "chat_completed"}
                    else "work"
                )
                self._add_activity(str(text), kind=kind)
            elif event_type == "CHAT_AI" and text:
                self.add_message("assistant", str(text))
                self._add_activity("Resposta publicada no chat.", kind="ok")
            elif event_type in {"SYSTEM_ALERT", "ADMIN_ACTION"} and text:
                self.add_message("system", str(text))
                self._add_activity(str(text), kind="warn")
            elif event_type == "TOOL_LOG":
                tool = event.get("tool", "ferramenta")
                stage = event.get("stage", "evento")
                self._add_activity(f"{tool}: {stage}", kind="work")
            elif event_type == "HUD_STATUS" and text:
                self.progress_label.setText(str(text))
                self._add_activity(str(text), kind="work")
            elif event_type == "EXECUTION_PENDING_APPROVAL":
                command = event.get("command", "")
                proposal_id = event.get("proposal_id", "")
                self.add_message(
                    "system",
                    "Execucao aguardando aprovacao.\n"
                    f"proposal_id: {proposal_id}\n"
                    f"comando: {command}\n"
                    "Responda Sim para aprovar.",
                )
                self._add_activity(f"Execucao pendente: {command}", kind="warn")
            elif event_type == "EXECUTION_UPDATE":
                stage = event.get("stage") or (event.get("payload") or {}).get(
                    "status"
                )
                proposal_id = event.get("proposal_id", "")
                self._add_activity(
                    f"Execucao {proposal_id}: {stage or 'atualizada'}",
                    kind="work",
                )

            self._prepend_event(event_type, str(text)[:180])

    def _prepend_event(self, event_type: str, detail: str) -> None:
        self.events_table.insertRow(0)
        self.events_table.setItem(0, 0, QTableWidgetItem(event_type))
        self.events_table.setItem(0, 1, QTableWidgetItem(detail))
        while self.events_table.rowCount() > 30:
            self.events_table.removeRow(self.events_table.rowCount() - 1)


def main() -> int:
    if "--check" in sys.argv:
        print("NEXUS Plasma GUI: Qt import ok")
        return 0

    def handle_exception(exc_type, exc, tb) -> None:
        log_path = ROOT_DIR / "logs" / "plasma_chat_crash.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fp:
            fp.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n")
            traceback.print_exception(exc_type, exc, tb, file=fp)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = handle_exception
    native_log = ROOT_DIR / "logs" / "plasma_chat_native.log"
    native_log.parent.mkdir(parents=True, exist_ok=True)
    native_fp = native_log.open("a", encoding="utf-8")
    native_fp.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] Plasma start\n")
    native_fp.flush()
    faulthandler.enable(file=native_fp, all_threads=True)
    atexit.register(
        lambda: (
            native_fp.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] Plasma exit\n"
            ),
            native_fp.flush(),
        )
    )
    app = QApplication(sys.argv)
    app.setApplicationName("NEXUS Plasma")
    app.setDesktopFileName("nexus-plasma-chat")
    app.setQuitOnLastWindowClosed(False)
    window = PlasmaChatWindow()
    window.show()
    if "--smoke" in sys.argv:
        QTimer.singleShot(600, window.quit_app)
    return app.exec()


def _app_icon() -> QIcon:
    if ICON_PATH.exists():
        icon = QIcon(str(ICON_PATH))
        if not icon.isNull():
            return icon
    icon = QIcon.fromTheme("nexus-plasma-chat")
    if icon.isNull():
        icon = QIcon.fromTheme("plasma")
    if icon.isNull():
        icon = QIcon.fromTheme("applications-system")
    return icon


def _find_audio_player() -> str | None:
    for name in ("ffplay", "mpv", "vlc", "dragon", "elisa", "xdg-open"):
        for folder in os.getenv("PATH", "").split(os.pathsep):
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
