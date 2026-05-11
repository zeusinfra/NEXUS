import json
import os
import threading
import urllib.request
import subprocess
import re
from zeus_core.observability import get_logger

logger = get_logger("zeus.peripherals.bluetooth_monitor")
BACKEND = os.getenv("NEXUS_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")


class BluetoothMonitor:
    """Monitora Bluetooth usando 'bluetoothctl monitor' (sem dependência de DBus/GI)."""

    def __init__(self):
        self._running = False
        self._process = None

    def start(self):
        """Inicia o monitoramento via subprocesso."""
        self._running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        logger.info("Monitor Bluetooth (Native) iniciado.")

    def _monitor_loop(self):
        try:
            # bluetoothctl monitor fornece logs em tempo real de eventos do BlueZ
            self._process = subprocess.Popen(
                ["bluetoothctl", "monitor"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            while self._running:
                line = self._process.stdout.readline()
                if not line:
                    break

                # Detectar conexões e desconexões via Regex simples
                # Exemplo: [CHG] Device 00:00:00:00:00:00 Connected: yes
                if "Connected: yes" in line:
                    self._handle_event(line, "CONECTADO")
                elif "Connected: no" in line:
                    self._handle_event(line, "DESCONECTADO")
                elif "Paired: yes" in line:
                    self._handle_event(line, "PAREADO")

        except Exception as e:
            logger.error(f"Erro no loop Bluetooth: {e}")

    def _handle_event(self, line, status):
        # Tentar extrair o endereço MAC
        mac_match = re.search(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", line, re.I)
        address = mac_match.group(0) if mac_match else "Desconhecido"

        msg = f"🛡️ BLUETOOTH: Dispositivo {address} está agora {status}."
        logger.info(msg)
        self._announce(msg)

    def _announce(self, text):
        def worker():
            try:
                # Chat
                payload = {
                    "message": text,
                    "source": "system_peripherals",
                    "client_id": "bluetooth_monitor",
                }
                req = urllib.request.Request(
                    f"{BACKEND}/api/chat",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)

                # TTS
                tts_payload = {"text": text.replace("🛡️ ", "")}
                tts_req = urllib.request.Request(
                    f"{BACKEND}/api/tts",
                    data=json.dumps(tts_payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(tts_req, timeout=5)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()


bluetooth_monitor = BluetoothMonitor()
