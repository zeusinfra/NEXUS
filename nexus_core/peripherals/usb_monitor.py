from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

try:
    import pyudev
except ImportError:  # pragma: no cover - depends on Linux desktop package set
    pyudev = None

from nexus_core.events.event_bus import EventType, event_bus
from nexus_core.observability import get_logger


BACKEND = os.getenv("NEXUS_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")
DEBOUNCE_SEC = float(os.getenv("NEXUS_USB_DEBOUNCE_SEC", "8.0") or "8.0")
GLOBAL_ANNOUNCE_COOLDOWN_SEC = float(
    os.getenv("NEXUS_USB_GLOBAL_COOLDOWN_SEC", "4.0") or "4.0"
)

logger = get_logger("nexus.peripherals.usb_monitor")


@dataclass(frozen=True)
class USBDeviceAnalysis:
    manufacturer: str
    model: str
    serial: str
    vendor_id: str
    product_id: str
    device_type: str
    risk: str
    action: str
    reason: str
    fingerprint: str


class USBMonitor:
    """Monitor USB em tempo real com triagem de risco estilo sentinela."""

    def __init__(self):
        self.context = None
        self.monitor = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_seen: dict[str, float] = {}
        self._last_announce_at = 0.0

    def start(self):
        """Inicia o monitoramento em uma thread separada."""
        if self._running:
            return
        if not self._ensure_monitor():
            if pyudev is None:
                logger.warning("Monitor USB indisponivel: pyudev nao esta instalado.")
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Monitor USB iniciado.")

    def stop(self):
        self._running = False

    def _ensure_monitor(self) -> bool:
        if self.monitor is not None:
            return True
        if pyudev is None:
            return False
        try:
            self.context = pyudev.Context()
            self.monitor = pyudev.Monitor.from_netlink(self.context)
            self.monitor.filter_by(subsystem="usb")
            return True
        except OSError as exc:
            logger.warning("Monitor USB indisponivel: %s", exc)
            self.context = None
            self.monitor = None
            return False

    def analyze_device(self, device: Any) -> USBDeviceAnalysis:
        """Analisa o dispositivo e retorna um relatorio de risco."""
        props = _props(device)
        manufacturer = _first(
            props,
            "ID_VENDOR_FROM_DATABASE",
            "ID_VENDOR",
            "MANUFACTURER",
            default="Fabricante desconhecido",
        )
        model = _first(
            props,
            "ID_MODEL_FROM_DATABASE",
            "ID_MODEL",
            "PRODUCT",
            default="Modelo desconhecido",
        )
        vendor_id = _first(props, "ID_VENDOR_ID", default="unknown")
        product_id = _first(props, "ID_MODEL_ID", default="unknown")
        serial = _first(props, "ID_SERIAL_SHORT", "ID_SERIAL", default="sem-serial")
        interfaces = _first(props, "ID_USB_INTERFACES", default="").lower()
        driver = _first(props, "ID_USB_DRIVER", default="").lower()
        devtype = _first(
            props, "DEVTYPE", default=getattr(device, "device_type", "") or ""
        ).lower()
        subsystem = (getattr(device, "subsystem", "") or "").lower()
        fingerprint = self._fingerprint_from_props(props)

        device_type = "USB generico"
        risk = "LOW"
        reason = "Dispositivo USB comum detectado."
        action = "Registrar evento, anunciar ao usuario e manter monitoramento passivo."

        if driver == "usb-storage" or devtype in {"partition", "disk"}:
            device_type = "Armazenamento USB"
            risk = "MEDIUM"
            reason = (
                "Midia removivel pode carregar malware, scripts ou arquivos suspeitos."
            )
            action = "Registrar a midia, evitar auto-execucao e recomendar varredura antes de abrir arquivos."
        elif _has_interface_class(interfaces, "03") or subsystem == "input":
            device_type = "HID USB"
            risk = "MEDIUM"
            reason = "Teclados e dispositivos HID podem simular entrada humana, incluindo ataques BadUSB."
            action = "Monitorar como dispositivo de entrada e alertar sobre comportamento inesperado."
        elif (
            _has_interface_class(interfaces, "e0")
            or _has_interface_class(interfaces, "ef")
            or _has_interface_class(interfaces, "02")
        ):
            device_type = "Rede ou comunicacao USB"
            risk = "HIGH"
            reason = "Adaptadores de rede/modem USB podem criar novas interfaces de comunicacao."
            action = "Alertar prioridade alta e recomendar conferir interfaces de rede antes de confiar no dispositivo."
        elif _has_interface_class(interfaces, "08"):
            device_type = "Armazenamento USB"
            risk = "MEDIUM"
            reason = "Interface USB Mass Storage detectada."
            action = "Registrar a midia, evitar auto-execucao e recomendar varredura antes de abrir arquivos."
        elif _has_interface_class(interfaces, "0e") or _has_interface_class(
            interfaces, "01"
        ):
            device_type = "Audio ou video USB"
            risk = "LOW"
            reason = "Dispositivo de captura/reproducao detectado."
            action = "Registrar e manter monitoramento passivo."

        if serial == "sem-serial" and risk == "LOW":
            risk = "MEDIUM"
            reason = f"{reason} O dispositivo nao informou serial, o que reduz rastreabilidade."

        return USBDeviceAnalysis(
            manufacturer=_clean(manufacturer),
            model=_clean(model),
            serial=_clean(serial),
            vendor_id=_clean(vendor_id),
            product_id=_clean(product_id),
            device_type=device_type,
            risk=risk,
            action=action,
            reason=reason,
            fingerprint=fingerprint,
        )

    def _monitor_loop(self):
        assert self.monitor is not None
        try:
            for device in iter(self.monitor.poll, None):
                if not self._running:
                    break
                if getattr(device, "action", None) == "add":
                    self._handle_add(device)
                elif getattr(device, "action", None) == "remove":
                    self._handle_remove(device)
        except Exception as exc:
            logger.error("Erro no loop do monitor USB: %s", exc)
            self._running = False

    def _handle_add(self, device: Any):
        if not self._is_primary_usb_event(device):
            return
        analysis = self.analyze_device(device)
        if self._is_duplicate(analysis.fingerprint) or self._is_global_duplicate():
            return

        msg = (
            f"USB conectado: {analysis.manufacturer} {analysis.model}. "
            f"Tipo: {analysis.device_type}. Risco: {analysis.risk}. "
            f"Motivo: {analysis.reason} Acao: {analysis.action}"
        )
        logger.info(msg)
        self._announce("Sentinela USB", msg, analysis.risk)
        self._publish(EventType.PERIPHERAL_CONNECTED, {"device_info": asdict(analysis)})

    def _handle_remove(self, device: Any):
        if not self._is_primary_usb_event(device):
            return
        props = _props(device)
        model = _clean(
            _first(
                props, "ID_MODEL_FROM_DATABASE", "ID_MODEL", default="Dispositivo USB"
            )
        )
        fingerprint = self._fingerprint_from_props(props)
        if self._is_duplicate(f"remove:{fingerprint}") or self._is_global_duplicate():
            return
        msg = f"USB removido: {model}."
        logger.info(msg)
        self._announce("Sentinela USB", msg, "LOW")
        self._publish(EventType.PERIPHERAL_DISCONNECTED, {"model": model})

    def _is_primary_usb_event(self, device: Any) -> bool:
        props = _props(device)
        devtype = _first(
            props, "DEVTYPE", default=getattr(device, "device_type", "") or ""
        ).lower()
        if devtype and devtype != "usb_device":
            logger.debug("Evento USB auxiliar ignorado: DEVTYPE=%s", devtype)
            return False
        return True

    def _is_duplicate(self, fingerprint: str) -> bool:
        now = time.monotonic()
        last = self._last_seen.get(fingerprint, 0.0)
        self._last_seen[fingerprint] = now
        return now - last < DEBOUNCE_SEC

    def _is_global_duplicate(self) -> bool:
        now = time.monotonic()
        if now - self._last_announce_at < GLOBAL_ANNOUNCE_COOLDOWN_SEC:
            return True
        self._last_announce_at = now
        return False

    def _fingerprint_from_props(self, props: dict[str, Any]) -> str:
        vendor_id = _first(props, "ID_VENDOR_ID", default="unknown")
        product_id = _first(props, "ID_MODEL_ID", default="unknown")
        serial = _first(props, "ID_SERIAL_SHORT", "ID_SERIAL", default="sem-serial")
        return f"{vendor_id}:{product_id}:{serial}"

    def _publish(self, event_type: EventType, payload: dict[str, Any]):
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(
                    event_bus.publish_async(event_type, payload)
                )
            )

    def _announce(self, title: str, text: str, severity: str):
        """Envia alerta local para a Web GUI e TTS."""

        def worker():
            payload = {
                "title": title,
                "message": text,
                "severity": severity.lower(),
                "source": "usb_monitor",
                "speak": True,
            }
            try:
                req = urllib.request.Request(
                    f"{BACKEND}/api/system/alert",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
                return
            except Exception as exc:
                logger.error("Erro ao enviar alerta USB para backend: %s", exc)

            try:
                tts_req = urllib.request.Request(
                    f"{BACKEND}/api/tts",
                    data=json.dumps({"text": text}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(tts_req, timeout=5)
            except Exception as exc:
                logger.error("Erro ao anunciar USB por TTS: %s", exc)

        threading.Thread(target=worker, daemon=True).start()


def _props(device: Any) -> dict[str, Any]:
    properties = getattr(device, "properties", None)
    if properties is None:
        return {}
    return dict(properties)


def _first(props: dict[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = props.get(key)
        if value:
            return str(value)
    return default


def _clean(value: str) -> str:
    return value.replace("_", " ").strip()[:160] or "Desconhecido"


def _has_interface_class(interfaces: str, class_code: str) -> bool:
    wanted = class_code.lower()
    return any(
        part.lower().startswith(wanted) for part in interfaces.split(":") if part
    )


usb_monitor = USBMonitor()
