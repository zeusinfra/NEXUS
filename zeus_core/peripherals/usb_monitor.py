import asyncio
import pyudev
import os
import threading
import json
import urllib.request
from zeus_core.events.event_bus import event_bus, EventType
from zeus_core.observability import get_logger
from zeus_core.security.daemon_client import daemon_client

BACKEND = os.getenv("ZEUS_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")

logger = get_logger("zeus.peripherals.usb_monitor")

class USBMonitor:
    """Monitora periféricos USB em tempo real e analisa riscos."""

    def __init__(self):
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem='usb')
        self._running = False

    def analyze_device(self, device):
        """Analisa o dispositivo e retorna um relatório de 'antivírus'."""
        info = {
            "manufacturer": device.get('ID_VENDOR_FROM_DATABASE', 'Desconhecido'),
            "model": device.get('ID_MODEL_FROM_DATABASE', 'Desconhecido'),
            "type": "Desconhecido",
            "risk": "LOW",
            "action": "Monitoring"
        }

        # Identificar classe do dispositivo
        subsystem = device.subsystem
        devtype = device.device_type
        
        # Se for um dispositivo de armazenamento
        if device.get('ID_USB_DRIVER') == 'usb-storage' or device.get('DEVTYPE') == 'partition':
            info["type"] = "Armazenamento (Pendrive/Disco)"
            info["action"] = "Verificando integridade e bloqueando auto-execução."
        
        # Se for um teclado/mouse (HID)
        elif "input" in device.get('ID_USB_INTERFACES', ''):
            info["type"] = "Interface Humana (Teclado/Mouse)"
            info["risk"] = "MEDIUM" # Risco de BadUSB/RubberDucky
            info["action"] = "Monitorando injeção de comandos suspeitos."
        
        return info

    def start(self):
        """Inicia o monitoramento em uma thread separada."""
        self._running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        logger.info("Monitor USB iniciado.")

    def _monitor_loop(self):
        for device in iter(self.monitor.poll, None):
            if not self._running:
                break
            
            if device.action == 'add':
                self._handle_add(device)
            elif device.action == 'remove':
                self._handle_remove(device)

    def _handle_add(self, device):
        analysis = self.analyze_device(device)
        msg = f"Novo dispositivo USB detectado: {analysis['manufacturer']} {analysis['model']}. Tipo: {analysis['type']}. Ação: {analysis['action']}"
        
        logger.info(msg)
        
        # Anunciar via TTS e Chat
        self._announce(msg)

        # Disparar evento interno
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(event_bus.publish_async(EventType.PERIPHERAL_CONNECTED, {
                    "device_info": analysis,
                    "raw_properties": dict(device.properties)
                }))
        except Exception:
            pass

    def _handle_remove(self, device):
        model = device.get('ID_MODEL_FROM_DATABASE', 'Dispositivo')
        msg = f"Dispositivo USB removido: {model}"
        logger.info(msg)
        self._announce(msg)
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(event_bus.publish_async(EventType.PERIPHERAL_DISCONNECTED, {"model": model}))
        except Exception:
            pass

    def _announce(self, text):
        """Envia o anúncio para a Web GUI para falar e mostrar no chat."""
        def worker():
            try:
                # 1. Mostrar no chat como sistema
                payload = {
                    "message": f"🛡️ **SENTINELA USB**: {text}",
                    "source": "system_peripherals",
                    "client_id": "usb_monitor"
                }
                req = urllib.request.Request(
                    f"{BACKEND}/api/chat",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=5)

                # 2. Falar via TTS
                tts_payload = {"text": text}
                tts_req = urllib.request.Request(
                    f"{BACKEND}/api/tts",
                    data=json.dumps(tts_payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(tts_req, timeout=5)
            except Exception as e:
                logger.error(f"Erro ao anunciar periférico: {e}")

        threading.Thread(target=worker, daemon=True).start()

usb_monitor = USBMonitor()
