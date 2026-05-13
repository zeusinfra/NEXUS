#!/usr/bin/env python3
from __future__ import annotations

import json
import base64
import os
import subprocess
import sys
import tempfile
import time
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
        self.setMinimumSize(980, 680)
        self.resize(1180, 760)

        self._workers: list[ApiWorker] = []
        self._seen_event_keys: set[str] = set()
        self._sending = False
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

        title = QLabel("NEXUS")
        title.setObjectName("brand")
        subtitle = QLabel("Plasma Command Surface")
        subtitle.setObjectName("subtitle")
        side_layout.addWidget(title)
        side_layout.addWidget(subtitle)

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

        self.progress_label = QLabel("Pronto.")
        self.progress_label.setObjectName("progress")
        content_layout.addWidget(self.progress_label)

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
            "NEXUS Plasma pronto. Use Ctrl+Enter para enviar. Voz ligada.",
        )

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QIcon.fromTheme("plasma")
        if icon.isNull():
            icon = QIcon.fromTheme("applications-system")
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("NEXUS Plasma")
        menu = QMenu()
        show_action = QAction("Mostrar", self)
        show_action.triggered.connect(self.show_normal)
        menu.addAction(show_action)
        status_action = QAction("Recarregar status", self)
        status_action.triggered.connect(self.refresh_status)
        menu.addAction(status_action)
        quit_action = QAction("Sair", self)
        quit_action.triggered.connect(QApplication.instance().quit)
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

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
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
        super().closeEvent(event)

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

    def _start_worker(
        self,
        name: str,
        method: str,
        path: str,
        payload: dict | None = None,
        timeout: float = 30.0,
    ) -> None:
        worker = ApiWorker(name, method, path, payload, timeout)
        worker.finished.connect(self._worker_finished)
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        worker.failed.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker: ApiWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
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
        self._sending = True
        self.send_button.setEnabled(False)
        self.progress_label.setText("Processando pedido...")
        payload = {
            "message": message,
            "client_msg_id": str(uuid.uuid4()),
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
        self._start_worker(
            "voice_start",
            "POST",
            "/api/applet/voice/start",
            {"duration": 10},
            timeout=10,
        )

    def ensure_backend(self) -> None:
        self.progress_label.setText("Garantindo backend...")
        try:
            subprocess.Popen(
                [str(ROOT_DIR / "bin" / "nexus"), "ensure-server"],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            self.add_message("error", f"Falha ao iniciar backend: {exc}")
            return
        QTimer.singleShot(1800, self.refresh_status)

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
            self.progress_label.setText("Resposta recebida.")
            reply = data.get("reply") or data.get("raw_reply") or "(sem resposta)"
            self._last_speech_text = str(data.get("speech_reply") or reply)
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
            else:
                self.add_message(
                    "system",
                    "TTS indisponivel. Instale edge-tts para gerar voz no backend.",
                )
        elif name == "voice_start":
            duration = data.get("duration", 10)
            self.progress_label.setText(f"Escuta armada por {duration}s.")

    def _worker_failed(self, name: str, error: str) -> None:
        if name == "health":
            self.connection_badge.setText("OFFLINE")
            self.connection_badge.setObjectName("badgeOffline")
            self.connection_badge.style().unpolish(self.connection_badge)
            self.connection_badge.style().polish(self.connection_badge)
            self.backend_label.setText(f"Backend: offline ({error})")
            return
        if name == "events":
            return
        if name == "chat":
            self._sending = False
            self.send_button.setEnabled(True)
            self.progress_label.setText("Falha no pedido.")
            self.add_message("error", error)
            return
        if name in {"tts", "voice_start"}:
            self.add_message("error", error)
            return
        self.progress_label.setText(error)

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
        self.progress_label.setText(f"Foco: {active}")

    def _render_events(self, events: list) -> None:
        for event in events:
            event_type = str(event.get("type") or "EVENT")
            text = (
                event.get("text")
                or event.get("message")
                or event.get("path")
                or event.get("stage")
                or event.get("status")
                or ""
            )
            key = str(event.get("id") or f"{event_type}:{text}:{time.time()}")
            if key in self._seen_event_keys:
                continue
            self._seen_event_keys.add(key)

            if event_type == "AGENT_PROGRESS" and text:
                self.progress_label.setText(str(text))
            elif event_type == "CHAT_AI" and text:
                self.add_message("assistant", str(text))
            elif event_type in {"SYSTEM_ALERT", "ADMIN_ACTION"} and text:
                self.add_message("system", str(text))

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

    app = QApplication(sys.argv)
    app.setApplicationName("NEXUS Plasma")
    app.setDesktopFileName("nexus-plasma-chat")
    app.setQuitOnLastWindowClosed(False)
    window = PlasmaChatWindow()
    window.show()
    if "--smoke" in sys.argv:
        QTimer.singleShot(600, app.quit)
    return app.exec()


def _find_audio_player() -> str | None:
    for name in ("ffplay", "mpv", "vlc", "dragon", "elisa", "xdg-open"):
        for folder in os.getenv("PATH", "").split(os.pathsep):
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
