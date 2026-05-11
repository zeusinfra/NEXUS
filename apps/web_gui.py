import os
from zeus_core.env import load_project_env

load_project_env()

import time
import asyncio
import tempfile
import psutil
import sqlite3
import shutil
import subprocess
import base64
import importlib.util
import uuid
from pathlib import Path
from collections import Counter
from communication.voice_service import voice_service
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
from apps.realtime_hub import RealtimeDeps, RealtimeHub
from apps.status_routes import StatusRouteDeps, create_status_router
from apps.routes.cognition_routes import CognitionRouteDeps, create_cognition_router
from apps.routes.privacy_routes import PrivacyRouteDeps, create_privacy_router
from zeus_core.cognitive import CognitionService
from zeus_core.cognitive.cognitive_state import cognitive_state_manager
from zeus_core.cognitive.goal_engine import GoalEngine
from zeus_core.cognitive.user_profile_engine import record_interaction
from zeus_core.security.privacy_guard import PrivacyGuard
from apps.lifecycle_manager import LifecycleManager
from pattern_engine import PatternEngine
from apps.zeus_evolution import ZeusBrain
from zeus_core.core_system import call_cloud_llm, get_llm_status
from zeus_core.agent import Agent
from zeus_core.vector_memory import VectorMemory
from zeus_core.voice_sensing import VoiceSensing
from zeus_core.vision import (
    analyze_image_with_llm,
    analyze_with_ocr_fallback,
    is_tesseract_available,
    capture_screen,
)
from zeus_core.resource_control import ResourceControl
from zeus_core.long_term_memory import (
    extract_memory,
    format_memory_for_prompt,
    load_memory as load_long_memory,
    should_extract_memory,
    update_memory as update_long_memory,
)
from zeus_core.asr import transcribe_audio_bytes
from zeus_core.config_guard import (
    LanSecurityConfig,
    build_config_diagnostics,
    env_flag,
    validate_startup_config,
)
from zeus_core.event_pipeline import OverflowEventQueue, RustWatcherRunner
from zeus_core.llm_service import LLMService
from zeus_core.memory_manager import MemoryManager
from zeus_core.path_filters import is_runtime_noise_path
from zeus_core.response_text import display_text, speech_text
from zeus_core.rust_sensors import (
    RUST_SENSORS_AVAILABLE,
    get_os_snapshot as get_rust_os_snapshot,
)
from zeus_core.conversation.sqlite_conversation_memory import conversation_memory
from zeus_core.events.watcher import watch_vault
from zeus_core.events.sync_worker import sync_worker_loop
from zeus_core.events.sync_engine import (
    sync_synaptic_to_obsidian,
    sync_longterm_to_notion,
    sync_insights_to_linear,
)
from zeus_core.cognitive.context_engine import build_current_context
from zeus_core.memory.sqlite_memory import get_connection as get_second_brain_connection
from zeus_core.health_status import (
    build_external_watcher_status,
    build_runtime_health,
    build_watcher_status,
)
from zeus_core.observability import (
    correlation_id_middleware,
    get_logger,
    get_metrics_snapshot,
    log_event,
    setup_logging,
)
from zeus_core.security_guard import (
    extract_bearer_token,
    is_local_host,
    is_local_request,
    is_trusted_host,
    is_trusted_request,
    require_lan_token_for_request,
    require_lan_token_for_socketio,
)
from zeus_core.security.daemon_client import daemon_client
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import RedirectResponse
import socketio

from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel

setup_logging(os.getenv("ZEUS_LOG_LEVEL", "INFO"))
logger = get_logger("zeus.web")

# --- CONFIGURAÇÕES ---
WATCH_DIRS = [str(PROJECT_ROOT)]
BASE_DIR = str(PROJECT_ROOT)
DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8080",
    "https://127.0.0.1:8080",
    "http://localhost:8080",
    "https://localhost:8080",
]
_env_flag = env_flag

ALLOW_LAN = _env_flag("ZEUS_ALLOW_LAN", "0")
DISABLE_SSL = _env_flag("ZEUS_DISABLE_SSL", "0")
print(f"DEBUG: ALLOW_LAN={ALLOW_LAN}, DISABLE_SSL={DISABLE_SSL}")

ENABLE_VOICE = _env_flag("ZEUS_ENABLE_VOICE", "1")
ENABLE_VOICE_SENSING = _env_flag("ZEUS_ENABLE_VOICE_SENSING", "0")
ENABLE_BROWSER_SENSING = _env_flag("ZEUS_ENABLE_BROWSER_SENSING", "0")
ENABLE_INTERNAL_WATCHER = _env_flag("ZEUS_ENABLE_INTERNAL_WATCHER", "0")
ENABLE_AUTONOMOUS_TASKS = _env_flag("ZEUS_ENABLE_AUTONOMOUS_TASKS", "0")
ENABLE_BOOT_GREETING = _env_flag("ZEUS_ENABLE_BOOT_GREETING", "0")
ENABLE_RESOURCE_MONITOR = _env_flag("ZEUS_ENABLE_RESOURCE_MONITOR", "0")
ENABLE_SECOND_BRAIN = _env_flag("ZEUS_ENABLE_SECOND_BRAIN", "0")
ENABLE_SECOND_BRAIN_SYNC_ENGINE = _env_flag("ZEUS_ENABLE_SECOND_BRAIN_SYNC_ENGINE", "0")
ENABLE_OBSIDIAN_AUTO_SYNC = _env_flag("ZEUS_ENABLE_OBSIDIAN_AUTO_SYNC", "0")
ENABLE_NOTION_AUTO_SYNC = _env_flag("ZEUS_ENABLE_NOTION_AUTO_SYNC", "0")
ENABLE_LINEAR_AUTO_SYNC = _env_flag("ZEUS_ENABLE_LINEAR_AUTO_SYNC", "0")
ENABLE_OPEN_FILE = _env_flag("ZEUS_ENABLE_OPEN_FILE", "0")
ENABLE_COGNITIVE_LOOP = _env_flag("ZEUS_COGNITIVE_LOOP_ENABLED", "0")
LAN_AUTH_ENABLED = _env_flag("ZEUS_LAN_AUTH", "1" if ALLOW_LAN else "0")
LAN_TOKEN = os.getenv("ZEUS_LAN_TOKEN", "").strip()

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ZEUS_ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS)
    ).split(",")
    if origin.strip()
]

SERVER_HOST = os.getenv("ZEUS_BIND_HOST", "0.0.0.0" if ALLOW_LAN else "127.0.0.1")
SERVER_PORT = int(os.getenv("ZEUS_PORT", "8080"))
PROJECT_COLORS = {
    "ZEUS_BRAIN": "#00f0ff",
    "GateStack": "#8c3cff",
    "ZEUS_SYSTEM": "#00ffcc",
    "zeus-rb": "#00ffcc",
    "zeus-portfolio": "#ff9628",
    "bot": "#ff3c50",
    "IA": "#00f0ff",
    "WEB_SENSING": "#ffd166",
    "OS_CORE": "#7ae582",
}
SCAN_BATCH_WINDOW = 0.18
EVENT_BATCH_WINDOW = 0.35
MAX_BATCH_EVENTS = 50
WS_BATCH_SAMPLE_LIMIT = 6
MEMORY_SAVE_INTERVAL_SECONDS = 12
MEMORY_SAVE_EVENT_DELTA = 20
MEMORY_DECAY_FACTOR = 0.98  # Fator de "esquecimento" aplicado em cada ciclo de limpeza
MAX_SYNAPTIC_PATHS = int(os.getenv("ZEUS_MAX_SYNAPTIC_PATHS", "20000") or "20000")
MAX_CONNECTIONS_PER_NODE = int(os.getenv("ZEUS_MAX_CONNECTIONS_PER_NODE", "25") or "25")
SYNAPTIC_PRUNE_INTERVAL_SECONDS = float(
    os.getenv("ZEUS_SYNAPTIC_PRUNE_INTERVAL_SECONDS", "60") or "60"
)
EVENT_QUEUE_MAXSIZE = int(os.getenv("ZEUS_EVENT_QUEUE_MAXSIZE", "2000") or "2000")
MAX_CHAT_MESSAGE_CHARS = int(
    os.getenv("ZEUS_MAX_CHAT_MESSAGE_CHARS", "16000") or "16000"
)
MAX_WEB_CONTEXT_CHARS = int(os.getenv("ZEUS_MAX_WEB_CONTEXT_CHARS", "50000") or "50000")
MAX_VISION_IMAGE_BYTES = int(
    os.getenv("ZEUS_MAX_VISION_IMAGE_BYTES", str(6 * 1024 * 1024))
    or str(6 * 1024 * 1024)
)

# Diretórios pesados a serem ignorados completamente
IGNORED_DIRS = {
    ".venv",
    "__pycache__",
    ".obsidian",
    ".git",
    "node_modules",
    "target",
    "dist",
    ".gemini",
    ".config",
    ".cache",
    "venv",
    ".rustup",
    ".cargo",
    ".npm",
    ".ruff_cache",
    "build",
    "CVS",
    ".svn",
    ".idea",
    ".vscode",
    "AppData",
    "Local",
    "Roaming",
}


def persist_memory_if_needed():
    # Deprecated: memory_manager handles persistence automatically via SQLite.
    pass


# --- STATE ---
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=ALLOWED_ORIGINS)

# Definindo variáveis de estado PRIMEIRO
realtime_hub = RealtimeHub(sio)
llm_service = LLMService(get_status=get_llm_status, call_llm=call_cloud_llm)
nodes_data = []
total_events = 0
recent_events_count = 0
system_mood = "CALM"
current_node = "N/A"
recent_events = []
recent_system_alerts: list[dict] = []
loop = None
event_pipeline = OverflowEventQueue(EVENT_QUEUE_MAXSIZE)
watcher_runner = RustWatcherRunner(PROJECT_ROOT)
_scan_lock = False  # Proteção contra scans simultâneos
MEMORY_FILE = os.path.join(BASE_DIR, "data", "synaptic_memory.json")
memory_manager = MemoryManager(db_path=os.path.join(BASE_DIR, "data", "zeus_memory.db"))
pattern_engine = PatternEngine(MEMORY_FILE)
brain = ZeusBrain()  # The Cognitive Core
vector_memory = VectorMemory(
    storage_file=os.path.join(BASE_DIR, "data", "vector_memory.json")
)
memory_manager.vector_memory = vector_memory
voice_module = VoiceSensing(wake_word=os.getenv("ZEUS_WAKE_WORD", "zeus"))
WATCH_ROOTS = [Path(path).resolve() for path in WATCH_DIRS if os.path.exists(path)]
long_term_memory = load_long_memory()
resource_control = ResourceControl(
    brain.blackboard, {}
)  # Integrando controle de recursos

lifecycle_manager = LifecycleManager(globals())
cognition_service = CognitionService()
privacy_guard = PrivacyGuard()
goal_engine = GoalEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop, _memory_save_lock
    loop = asyncio.get_running_loop()
    _memory_save_lock = asyncio.Lock()

    _validate_lan_security_config()

    # Carregar Memória Sináptica do disco
    load_memory()

    # Limpar arquivos temporários de voz antigos
    asyncio.create_task(cleanup_voice_temp_files())

    # Watcher interno fica opt-in; o launcher ja sobe o watcher Rust dedicado.
    if ENABLE_INTERNAL_WATCHER:
        asyncio.create_task(run_rust_watcher())

    # Monitorar navegações web apenas com opt-in explícito
    global _web_sensing_task
    if ENABLE_BROWSER_SENSING:
        _web_sensing_task = asyncio.create_task(lifecycle_manager.web_sensing_loop())

    # Inicia o batcher e tarefas proativas opcionais
    asyncio.create_task(event_batcher())
    if ENABLE_AUTONOMOUS_TASKS:
        asyncio.create_task(autonomous_audit())

    asyncio.create_task(metrics_loop())
    if ENABLE_RESOURCE_MONITOR:
        asyncio.create_task(resource_control.monitor_and_report())

    # Inicia o Sensing de Voz (apenas se disponível e habilitado)
    global _voice_task
    if ENABLE_VOICE and ENABLE_VOICE_SENSING:
        _voice_task = asyncio.create_task(lifecycle_manager.safe_voice_task())

    # Reflexao cognitiva autonoma fica opt-in no perfil applet/headless.
    if ENABLE_AUTONOMOUS_TASKS:
        asyncio.create_task(autonomous_reflection())

    # Guardião de low-mem (desativa features pesadas automaticamente)
    if LOW_MEM_AUTO:
        asyncio.create_task(lifecycle_manager.low_mem_guard())

    # Saudacao inicial com a cognicao
    if ENABLE_BOOT_GREETING:
        asyncio.create_task(lifecycle_manager.boot_greeting())

    # Iniciar Monitores de Periféricos (Sentinela)
    try:
        from zeus_core.peripherals.usb_monitor import usb_monitor
        from zeus_core.peripherals.bluetooth_monitor import bluetooth_monitor

        usb_monitor.start()
        bluetooth_monitor.start()
        logger.info("Sentinela USB/Bluetooth ativado no Backend.")
    except Exception as e:
        logger.error(f"Falha ao iniciar monitores no backend: {e}")

    # Second Brain Tasks
    global _watcher_task, _sync_worker_task, _sync_engine_tasks
    _watcher_task = None
    _sync_worker_task = None
    _sync_engine_tasks = []
    vault_path = os.getenv("ZEUS_VAULT_PATH", "/home/zeus/Documentos/Brain")
    if ENABLE_SECOND_BRAIN and os.path.exists(vault_path):
        print(f"[ZEUS] Iniciando Second Brain integrando {vault_path}")
        _watcher_task = asyncio.create_task(watch_vault(vault_path))
        _sync_worker_task = asyncio.create_task(sync_worker_loop())
        if ENABLE_SECOND_BRAIN_SYNC_ENGINE or ENABLE_OBSIDIAN_AUTO_SYNC:
            print("[ZEUS] Iniciando Sync Engine: Sináptico→Obsidian")
            _sync_engine_tasks.append(
                asyncio.create_task(
                    sync_synaptic_to_obsidian(memory_manager, interval=60.0)
                )
            )
        if ENABLE_SECOND_BRAIN_SYNC_ENGINE or ENABLE_NOTION_AUTO_SYNC:
            print("[ZEUS] Iniciando Sync Engine: LongTerm→Notion")
            _sync_engine_tasks.append(
                asyncio.create_task(sync_longterm_to_notion(interval=300.0))
            )
        if ENABLE_SECOND_BRAIN_SYNC_ENGINE or ENABLE_LINEAR_AUTO_SYNC:
            print("[ZEUS] Iniciando Sync Engine: Insights→Linear")
            _sync_engine_tasks.append(
                asyncio.create_task(
                    sync_insights_to_linear(memory_manager, interval=300.0)
                )
            )

    # Cognitive Loop
    if ENABLE_COGNITIVE_LOOP:
        print("[ZEUS] Iniciando Cognitive Loop autônomo")
        await cognition_service.start()

    yield
    # Salvar Memória ao fechar
    save_memory()
    vector_memory.save()
    # Cancelar tasks opcionais
    try:
        if _web_sensing_task:
            _web_sensing_task.cancel()
    except Exception:
        pass
    try:
        if _voice_task:
            _voice_task.cancel()
    except Exception:
        pass
    try:
        if _watcher_task:
            _watcher_task.cancel()
        if _sync_worker_task:
            _sync_worker_task.cancel()
        for task in _sync_engine_tasks:
            task.cancel()
    except Exception:
        pass
    # Stop cognitive loop
    try:
        if cognition_service.is_running:
            await cognition_service.stop()
    except Exception:
        pass


app = FastAPI(lifespan=lifespan)
app.middleware("http")(correlation_id_middleware)


indexing_semaphore = asyncio.Semaphore(2)  # Limite de indexação simultânea
LOW_MEM_AUTO = _env_flag("ZEUS_LOW_MEM_AUTO", "1")
LOW_MEM_ENTER_RAM = float(os.getenv("ZEUS_LOW_MEM_ENTER_RAM", "82") or "82")
LOW_MEM_EXIT_RAM = float(os.getenv("ZEUS_LOW_MEM_EXIT_RAM", "72") or "72")
LOW_MEM_ACTIVE = False
_voice_task = None
_web_sensing_task = None

# Sensores Web
LAST_WEB_URL = ""

# Motor ReAct (Tool Calling)
react_agent = Agent()


async def enqueue_event(event: dict) -> None:
    await event_pipeline.enqueue(event)


async def speak(text, target: str = "all"):
    """Toca TTS local (Edge-TTS + ffplay) via VoiceSensing quando habilitado."""
    if not text or not text.strip():
        return
    spoken_text = speech_text(text)
    display_reply = display_text(text)
    try:
        if not ENABLE_VOICE:
            # Em modo somente texto, apenas loga
            print(f"[ZEUS VOICE ALERT] {display_reply or text}")
            return

        # Envia o comando de voz para a Bolha/Web via Socket.io
        await broadcast_message(
            {
                "type": "voice_play",
                "text": spoken_text or text,
                "raw_text": text,
                "voice": "pt-BR-AntonioNeural",
                "target": target,
            }
        )

        # Mantém a fala no servidor quando habilitado
        await voice_module.speak(spoken_text or text)
    except Exception as e:
        print(f"[ZEUS] Falha ao falar (fallback para log): {e}")
        print(f"[ZEUS VOICE ALERT] {display_reply or text}")


async def cleanup_voice_temp_files():
    pass


def _is_local_request(request: Request) -> bool:
    return is_local_request(request)


def _is_trusted_host(host: str | None) -> bool:
    return is_trusted_host(host, allow_lan=ALLOW_LAN)


def _is_trusted_request(request: Request) -> bool:
    return is_trusted_request(request, allow_lan=ALLOW_LAN)


def _is_local_host(host: str | None) -> bool:
    return is_local_host(host)


def _remote_auth_required() -> bool:
    return ALLOW_LAN or not _is_local_host(SERVER_HOST)


def _extract_bearer_token(value: str | None) -> str | None:
    return extract_bearer_token(value)


def _require_lan_token_for_request(request: Request) -> None:
    """
    Quando ZEUS_ALLOW_LAN=1, exige token para chamadas vindas de hosts não-locais.
    Objetivo: evitar que qualquer device na LAN tenha acesso ao core.
    """
    require_lan_token_for_request(request, lan=_build_lan_security_config())


def _require_lan_token_for_socketio(environ: dict, auth_payload: dict | None) -> bool:
    return require_lan_token_for_socketio(
        environ, auth_payload, lan=_build_lan_security_config()
    )


def _validate_lan_security_config() -> None:
    """Validate security when remote access is enabled by config or bind host."""
    validate_startup_config(lan=_build_lan_security_config())


def _build_lan_security_config() -> LanSecurityConfig:
    return LanSecurityConfig(
        allow_lan=ALLOW_LAN,
        lan_auth_enabled=LAN_AUTH_ENABLED,
        lan_token=LAN_TOKEN,
        bind_host=SERVER_HOST,
    )


def _resolve_user_path(path: str) -> Path | None:
    try:
        candidate = Path(path).expanduser().resolve()
    except Exception:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    for root in WATCH_ROOTS:
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    return None


def open_file_in_editor(path):
    """Abre o arquivo no editor padrão do sistema."""
    if not ENABLE_OPEN_FILE:
        return False
    try:
        # Tenta abrir com xdg-open (padrão Linux)
        subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception as e:
        print(f"Error opening file: {e}")
        return False


def get_browser_history():
    """Tenta ler a última URL visitada do Chrome/Chromium."""
    global LAST_WEB_URL
    if not ENABLE_BROWSER_SENSING:
        return None
    # Caminhos comuns para Chromium-based browsers no Linux
    paths = [
        os.path.expanduser("~/.config/google-chrome/Default/History"),
        os.path.expanduser("~/.config/brave-browser/Default/History"),
        os.path.expanduser("~/.config/microsoft-edge/Default/History"),
    ]

    for path in paths:
        if os.path.exists(path):
            try:
                # O SQLite trava o arquivo se o browser estiver aberto. Copiamos para ler.
                with tempfile.NamedTemporaryFile(
                    prefix="zeus_web_history_", delete=False
                ) as temp_file:
                    temp_history = temp_file.name
                shutil.copy2(path, temp_history)
                conn = sqlite3.connect(temp_history)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT url FROM urls ORDER BY last_visit_time DESC LIMIT 1"
                )
                row = cursor.fetchone()
                conn.close()
                try:
                    os.unlink(temp_history)
                except OSError:
                    pass
                if row:
                    url = row[0]
                    if url != LAST_WEB_URL:
                        LAST_WEB_URL = url
                        return url
            except Exception:
                continue
    return None


def classify_web_context(url: str):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    category = "web"
    if any(token in domain for token in ["github", "gitlab", "bitbucket"]):
        category = "dev"
    elif any(token in domain for token in ["docs", "readthedocs", "developer"]):
        category = "docs"
    elif any(
        token in domain for token in ["youtube", "x.com", "twitter", "reddit", "news"]
    ):
        category = "media"
    elif any(token in domain for token in ["google", "duckduckgo", "bing"]):
        category = "search"
    return {
        "domain": domain or "unknown",
        "category": category,
        "path": parsed.path or "/",
    }


def get_os_snapshot():
    rust_snapshot = get_rust_os_snapshot()
    if rust_snapshot:
        return rust_snapshot

    cpu_per_core = psutil.cpu_percent(percpu=True)
    cpu_avg = sum(cpu_per_core) / len(cpu_per_core) if cpu_per_core else 0
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    process_rows = []
    try:
        # Pega todos os processos de uma vez para ser mais eficiente
        for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                cpu = info.get("cpu_percent") or 0.0
                mem = info.get("memory_percent") or 0.0
                if cpu < 1.0 and mem < 1.0:  # Ignora processos irrelevantes
                    continue
                process_rows.append(
                    {
                        "name": info.get("name") or "unknown",
                        "cpu": round(cpu, 1),
                        "memory": round(mem, 1),
                        "family": classify_process_family(
                            info.get("name") or "unknown"
                        ),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    process_rows.sort(key=lambda item: item["cpu"], reverse=True)
    pressure = "calm"
    if cpu_avg > 80 or ram > 85 or disk > 92:
        pressure = "critical"
    elif cpu_avg > 55 or ram > 70:
        pressure = "active"
    elif cpu_avg > 25 or ram > 55:
        pressure = "stable"
    return {
        "cpu_per_core": cpu_per_core,
        "cpu_avg": round(cpu_avg, 1),
        "ram": ram,
        "disk": disk,
        "top_processes": process_rows[:3],
        "pressure": pressure,
    }


def classify_process_family(name: str):
    normalized = (name or "").lower()
    if any(token in normalized for token in ["chrome", "brave", "firefox", "edge"]):
        return "browser"
    if any(token in normalized for token in ["code", "nvim", "vim", "pycharm", "idea"]):
        return "editor"
    if any(
        token in normalized
        for token in ["python", "node", "bun", "cargo", "rust", "java"]
    ):
        return "runtime"
    if any(token in normalized for token in ["docker", "podman", "qemu", "vm"]):
        return "infra"
    if any(
        token in normalized
        for token in ["pipewire", "pulseaudio", "wireplumber", "spotify", "vlc"]
    ):
        return "media"
    return "system"


def load_memory():
    # Deprecated: MemoryManager initializes SQLite automatically.
    pass


def save_memory():
    # Deprecated: SQLite is auto-committing or handled by MemoryManager.
    pass


def prune_synaptic_memory(*, force: bool = False) -> None:
    # MemoryManager handles decay automatically via decay_memory().
    memory_manager.decay_memory(factor=0.98)


def persist_memory_if_needed(force: bool = False):
    # Deprecated: memory_manager handles persistence automatically via SQLite.
    pass


async def _safe_save_memory():
    """Serializa as escritas de memória para evitar corrupção de JSON."""
    # Deprecated: SQLite is atomic. Only vector memory needs explicit saving if modified.
    await asyncio.to_thread(vector_memory.save)


async def update_nodes_on_event(event):
    global nodes_data
    path = event["path"]
    if is_runtime_noise_path(path):
        return

    # Record sensation in L1
    memory_manager.record_sensation(event)

    # Update synapse/node in L2
    memory_manager.update_synapse(path, path)  # Self-update weight

    if event["event"] == "SCAN" or event["event"] == "Create":
        # Get weight from L2
        conn = sqlite3.connect(memory_manager.db_path)
        c = conn.cursor()
        c.execute("SELECT weight FROM nodes WHERE path = ?", (path,))
        row = c.fetchone()
        weight = row[0] if row else 1
        conn.close()

        nodes_data.append(
            {
                "rel": path,
                "name": os.path.basename(path),
                "project": event["project"],
                "color": get_project_color(event["project"]),
                "weight": weight,
                "cluster": get_node_cluster(path),
            }
        )
        # Indexar conteúdo para memória semântica
        if os.path.exists(path):
            asyncio.create_task(throttled_index_file(path))

    if len(nodes_data) > 1000:
        nodes_data = nodes_data[-1000:]


async def throttled_index_file(path):
    """Indexa um arquivo respeitando o limite de concorrência."""
    async with indexing_semaphore:
        try:
            # Throttle: Se o sistema estiver crítico, aguarda antes de indexar
            while resource_control.is_critical():
                print(
                    f"[ZEUS RESOURCE ALERT] High pressure detected. Indexing paused for {path}..."
                )
                await asyncio.sleep(5.0)

            await asyncio.to_thread(vector_memory.index_file, path)
        except Exception as e:
            print(f"Error in throttled index for {path}: {e}")


# Inicializa o psutil com uma leitura base (necessário para leituras futuras serem precisas)
psutil.cpu_percent(percpu=True)


def get_project(path):
    # Tenta identificar o projeto baseado no caminho absoluto
    for wd in WATCH_DIRS:
        if path.startswith(wd):
            root_name = os.path.basename(wd.rstrip(os.sep)) or "ZEUS_SYSTEM"
            rel = os.path.relpath(path, wd)
            parts = rel.split(os.sep)
            if "ZEUS_BRAIN" in wd:
                return "ZEUS_BRAIN"
            if parts and parts[0] not in {"", "."} and len(parts) > 1:
                return parts[0]
            return root_name
    return "unknown"


def get_project_color(project_name):
    return PROJECT_COLORS.get(project_name, "#46465a")


def get_node_cluster(path: str) -> str:
    """Atribui um nó a um cluster fixo com base no conteúdo/caminho."""
    path_lower = path.lower()
    if any(
        ext in path_lower
        for ext in [".py", ".rs", ".js", ".ts", ".tsx", ".html", ".css", ".md"]
    ):
        return "files"
    if "http" in path_lower or "www" in path_lower:
        return "web"
    if any(
        token in path_lower
        for token in ["bin", "etc", "var", "system", "kernel", "proc"]
    ):
        return "os"
    if any(token in path_lower for token in ["chat", "conv", "messages", "prompts"]):
        return "chat"
    return "memory"


def build_project_activity():
    activity = {project: 0 for project in PROJECT_COLORS.keys()}
    for node in nodes_data:
        project = node.get("project", "unknown")
        activity[project] = activity.get(project, 0) + 1
    return activity


def build_memory_summary():
    conn = sqlite3.connect(memory_manager.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM nodes")
    learned_paths = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(weight) FROM synapses")
    connection_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT path, weight FROM nodes ORDER BY weight DESC LIMIT 1")
    row = cursor.fetchone()
    hottest_path, hottest_weight = row if row else (None, 0)

    conn.close()

    recall_index = min(
        100, round((connection_total * 2 + hottest_weight) / max(1, learned_paths))
    )
    memory_density = round(connection_total / max(1, learned_paths), 2)
    return {
        "learned_paths": learned_paths,
        "connection_total": connection_total,
        "hottest_path": hottest_path,
        "hottest_weight": hottest_weight,
        "recall_index": recall_index,
        "memory_density": memory_density,
    }


def _build_init_payload() -> dict:
    memory_summary = build_memory_summary()
    vision_caps = {
        "ocr_available": bool(is_tesseract_available()),
        "client_capture_available": True,
    }
    asr_caps = {
        "backend_asr_available": bool(shutil.which("ffmpeg"))
        and (importlib.util.find_spec("faster_whisper") is not None),
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
    }
    return {
        "type": "init_nodes",
        "node_count": len(nodes_data),
        "latest_node": nodes_data[-1]["rel"] if nodes_data else None,
        "memory_summary": memory_summary,
        "vision": vision_caps,
        "asr": asr_caps,
        "capabilities": _build_operational_capabilities(),
        "system_update": {
            "headline": "Warm boot neural",
            "detail": f"{memory_summary['learned_paths']} trilhas recuperadas do disco.",
        },
    }


def summarize_batch(events):
    file_events = [event for event in events if event.get("type") == "FILE_EVENT"]
    paths = [event.get("path") for event in file_events if event.get("path")]
    projects = Counter(event.get("project", "unknown") for event in file_events)
    kinds = Counter(event.get("event", "unknown") for event in file_events)
    dominant_project = projects.most_common(1)[0][0] if projects else "unknown"
    dominant_kind = kinds.most_common(1)[0][0] if kinds else "unknown"
    markdown_hits = sum(1 for path in paths if path.endswith(".md"))
    code_hits = sum(
        1
        for path in paths
        if path.endswith((".py", ".rs", ".js", ".ts", ".tsx", ".jsx", ".html", ".css"))
    )
    return {
        "event_count": len(file_events),
        "dominant_project": dominant_project,
        "dominant_kind": dominant_kind,
        "markdown_hits": markdown_hits,
        "code_hits": code_hits,
        "sample_paths": paths[:WS_BATCH_SAMPLE_LIMIT],
    }


async def run_rust_watcher():
    """Executes the Rust watcher and forwards events to the event_queue."""
    await watcher_runner.run(enqueue_event)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
public_dir = os.path.join(BASE_DIR, "public")
if not os.path.exists(public_dir):
    os.makedirs(public_dir)
app.mount("/static", StaticFiles(directory=public_dir), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/open-file")
async def open_file(data: dict, request: Request):
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="Only local requests are allowed.")
    _require_lan_token_for_request(request)

    path = data.get("path")
    if path:
        safe_path = _resolve_user_path(path)
        if safe_path is None:
            raise HTTPException(
                status_code=400, detail="Path is outside allowed watch roots."
            )
        if not ENABLE_OPEN_FILE:
            raise HTTPException(
                status_code=403, detail="Open-file integration is disabled."
            )
        success = open_file_in_editor(safe_path)
        return {"status": "success" if success else "error", "path": str(safe_path)}
    return {"status": "error", "message": "No path provided"}


@app.post("/ai-insight")
async def ai_insight(data: dict, request: Request):
    """
    Interfere na rede neural para gerar insights semânticos em PT-BR.
    """
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="Only local requests are allowed.")
    _require_lan_token_for_request(request)

    event_type = data.get("type")
    content = data.get("content") or ""

    insight = ""
    if event_type == "FILE_EVENT":
        if "core" in content.lower():
            insight = "Sinto que você está mexendo no núcleo do sistema. Tenha cuidado com as dependências."
        elif "web" in content.lower():
            insight = "A interface web está evoluindo. A sincronia visual parece ótima."
        else:
            insight = "Alteração detectada. O grafo sináptico está sendo atualizado."
    elif event_type == "WEB_EVENT":
        insight = f"Achei interessante essa navegação em {content}. Pode ser útil para o projeto."

    if insight:
        await speak(insight)
        await broadcast_message(
            {"type": "AI_INSIGHT", "message": insight, "mood": system_mood}
        )

    return {"insight": insight}


@app.post("/api/web-context")
async def receive_web_context(data: dict, request: Request):
    """
    Recebe contexto de extensões de navegador (URL, Título, Seleção de texto).
    """
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    url = str(data.get("url") or "").strip()
    title = str(data.get("title") or "").strip()[:300]
    content = str(data.get("content") or "")

    if not url:
        raise HTTPException(status_code=400, detail="No URL provided.")
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="URL too long.")
    if len(content) > MAX_WEB_CONTEXT_CHARS:
        content = content[:MAX_WEB_CONTEXT_CHARS]

    # Injeta como um evento de sistema
    event = {
        "type": "FILE_EVENT",
        "event": "WEB_SENSE",
        "path": url,
        "project": "WEB_SENSING",
    }
    await enqueue_event(event)

    # Se houver conteúdo relevante, indexa o texto na memória semântica
    if len(content) > 50:
        web_key = f"WEB_DOC: {title} ({url})"
        await asyncio.to_thread(vector_memory.index_text, web_key, content)

    await broadcast_message(
        {
            "type": "WEB_EVENT",
            "url": url,
            "title": title,
            "log": {
                "channel": "web",
                "title": "Consciência Web Expandida",
                "detail": f"ZEUS assimilou conteúdo de: {title or url}",
                "meta": f"length={len(content)}",
            },
        }
    )

    return {"status": "success"}


@app.get("/status")
async def get_status(request: Request):
    _require_lan_token_for_request(request)
    client_id = request.headers.get("x-zeus-client-id")

    cpu_per_core = psutil.cpu_percent(percpu=True)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    # Collect pending messages for this client
    pending_msgs = realtime_hub.drain_inbox(client_id)

    return {
        "cpu": cpu_per_core,
        "ram": ram,
        "disk": disk,
        "total_events": total_events,
        "mood": system_mood,
        "active_path": nodes_data[-1]["rel"] if nodes_data else "ZEUS_SYSTEM / IDLE",
        "project_activity": build_project_activity(),
        "messages": pending_msgs,
    }


@app.get("/api/events/drain")
async def api_events_drain(request: Request, client_id: str | None = None):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    resolved_client_id = (
        client_id or request.headers.get("x-zeus-client-id") or ""
    ).strip()[:64]
    if not resolved_client_id:
        raise HTTPException(status_code=400, detail="client_id is required.")

    realtime_hub.client_inboxes.setdefault(resolved_client_id, [])
    return {
        "client_id": resolved_client_id,
        "events": realtime_hub.drain_inbox(resolved_client_id),
    }


async def broadcast_message(msg: dict):
    await realtime_hub.broadcast_message(msg)


async def voice_context_trigger(text: str, channel: str = "system"):
    """Gera um alerta de voz contextualizado."""
    if not ENABLE_VOICE or not text or not text.strip():
        return

    prefix = {
        "cognitive": "Sussurro cerebral: ",
        "signal": "Sinal detectado: ",
        "os": "Alerta de sistema: ",
        "system": "ZEUS informa: ",
    }.get(channel, "")

    full_text = f"{prefix}{text}"
    await speak(full_text)


async def event_batcher():
    global total_events, recent_events_count
    while True:
        events = []
        first_event = await event_pipeline.get()
        is_scan_burst = first_event.get("event") == "SCAN"
        batch_window = SCAN_BATCH_WINDOW if is_scan_burst else EVENT_BATCH_WINDOW

        if "type" in first_event and first_event["type"] == "FILE_EVENT":
            await update_nodes_on_event(first_event)
            total_events += 1
            recent_events_count += 1

        events.append(first_event)
        pulse_first = pattern_engine.process_event(first_event)

        await asyncio.sleep(batch_window)
        while not event_pipeline.empty() and len(events) < MAX_BATCH_EVENTS:
            ev = event_pipeline.get_nowait()

            if "type" in ev and ev["type"] == "FILE_EVENT":
                await update_nodes_on_event(ev)
                total_events += 1
                recent_events_count += 1
            events.append(ev)
            pattern_engine.process_event(ev)

        # PatternEngine now enriches the shared in-process state only.
        pattern_engine.sync_to_manager(memory_manager)

        # --- APRENDIZADO de CORRELAÇÃO ---
        file_paths = [e["path"] for e in events if "path" in e]
        if len(file_paths) > 1:
            for path in file_paths:
                for other_path in file_paths:
                    if path != other_path:
                        memory_manager.update_synapse(path, other_path)

        persist_memory_if_needed()

        if events:
            batch_summary = summarize_batch(events)
            memory_summary = build_memory_summary()

            # Determinar cluster dominante do lote
            paths = [e["path"] for e in events if "path" in e]
            dominant_cluster = "idle"
            if paths:
                cluster_counts = Counter([get_node_cluster(p) for p in paths])
                dominant_cluster = cluster_counts.most_common(1)[0][0]

            cluster_logs = {
                "files": f"Arquivos ({batch_summary['dominant_kind']}) dominando",
                "web": f"Web ({batch_summary.get('dominant_project', 'docs')}) ativo",
                "os": "SO (runtime) pressionando",
                "chat": "Chat (contexto) processando",
                "memory": "Memória (sinapse) consolidando",
            }

            if is_scan_burst:
                high_level_pulse = {
                    "type": "SYNAPSE_FIRE",
                    "node": first_event.get("path"),
                    "intensity": "medium" if len(events) < 12 else "high",
                    "source": "scan",
                    "signal_profile": batch_summary,
                }
                await broadcast_message(high_level_pulse)
                await broadcast_message(
                    {
                        "type": "FILE_EVENT_BATCH",
                        "mode": "scan",
                        "event_count": len(events),
                        "projects": sorted(
                            {e.get("project", "unknown") for e in events}
                        ),
                        "sample_paths": [
                            e.get("path")
                            for e in events[:WS_BATCH_SAMPLE_LIMIT]
                            if e.get("path")
                        ],
                        "signal_profile": batch_summary,
                        "memory_summary": memory_summary,
                        "active_cluster": dominant_cluster,
                        "log": {
                            "channel": "memory",
                            "title": "Scan assimilado",
                            "detail": cluster_logs.get(
                                dominant_cluster,
                                f"{batch_summary['event_count']} sinais incorporados.",
                            ),
                            "meta": f"kind={batch_summary['dominant_kind']} md={batch_summary['markdown_hits']} code={batch_summary['code_hits']}",
                        },
                    }
                )
            elif len(events) > 1:
                await broadcast_message(pulse_first)
                await broadcast_message(
                    {
                        "type": "FILE_EVENT_BATCH",
                        "mode": "live",
                        "event_count": len(events),
                        "events": events[:WS_BATCH_SAMPLE_LIMIT],
                        "signal_profile": batch_summary,
                        "memory_summary": memory_summary,
                        "active_cluster": dominant_cluster,
                        "log": {
                            "channel": "signal",
                            "title": f"Lote realtime em {batch_summary['dominant_project']}",
                            "detail": cluster_logs.get(
                                dominant_cluster,
                                f"{batch_summary['event_count']} eventos sincronizados.",
                            ),
                            "meta": f"kind={batch_summary['dominant_kind']} code={batch_summary['code_hits']}",
                        },
                    }
                )

                # Proatividade: Sugerir arquivos semanticamente próximos do arquivo mais recente
                suggestions = []
                last_path = paths[-1] if paths else None
                if last_path:
                    # Use find_similar_by_key to search by existing vector instead of path text
                    similar = await asyncio.to_thread(
                        vector_memory.find_similar_by_key, last_path, 2
                    )
                    if similar:
                        suggestions = [p for p, s in similar if p != last_path]
                if suggestions:
                    await broadcast_message(
                        {
                            "type": "PROACTIVE_SENSING",
                            "target": last_path,
                            "suggestions": suggestions,
                            "log": {
                                "channel": "cognitive",
                                "title": "Sussurro Semântico",
                                "detail": f"Detectei correlação profunda com {os.path.basename(suggestions[0])}.",
                                "meta": "vector_match=high",
                            },
                        }
                    )
                    await voice_context_trigger(
                        f"Detectei correlação profunda com {os.path.basename(suggestions[0])}",
                        "cognitive",
                    )

            else:
                await broadcast_message(pulse_first)
                await broadcast_message(
                    {
                        **events[0],
                        "active_cluster": dominant_cluster,
                        "log": {
                            "channel": "signal",
                            "title": "Sinal isolado",
                            "detail": cluster_logs.get(
                                dominant_cluster, "Sinal processado."
                            ),
                            "meta": f"cluster={dominant_cluster}",
                        },
                    }
                )


async def metrics_loop():
    global recent_events_count, system_mood
    while True:
        await asyncio.sleep(3.0)
        os_snapshot = await asyncio.to_thread(get_os_snapshot)
        cpu_per_core = os_snapshot["cpu_per_core"]
        cpu_avg = os_snapshot["cpu_avg"]
        ram_usage = os_snapshot["ram"]
        activity_spike = recent_events_count

        # Lógica de Reação Real baseada em Telemetria do OS
        if cpu_avg > 80 or ram_usage > 85:
            system_mood = "STRESSED"
        elif recent_events_count > 50:
            system_mood = "HYPERACTIVE"
        elif recent_events_count > 10:
            system_mood = "ACTIVE"
        elif recent_events_count > 0:
            system_mood = "EVOLVING"
        else:
            system_mood = "CALM"

        # Reseta o contador de eventos para a próxima janela de 3s
        recent_events_count = 0
        memory_summary = build_memory_summary()
        behavioral_state = pattern_engine.analyze_behavioral_state()

        msg = {
            "type": "METRICS",
            "cpu": cpu_per_core,
            "ram": ram_usage,
            "disk": os_snapshot["disk"],
            "mood": system_mood,
            "total_nodes": len(nodes_data),
            "total_events": total_events,
            "activity_spike": activity_spike,
            "behavioral_state": behavioral_state,
            "learning": {
                "learned_paths": memory_summary["learned_paths"],
                "connection_total": memory_summary["connection_total"],
                "recall_index": memory_summary["recall_index"],
                "memory_density": memory_summary["memory_density"],
                "hottest_path": memory_summary["hottest_path"],
                "hottest_weight": memory_summary["hottest_weight"],
                "save_age_seconds": round(time.time() - last_memory_save, 1)
                if last_memory_save
                else None,
            },
            "os_context": os_snapshot,
            "system_update": {
                "headline": f"Estado {behavioral_state.lower()}",
                "detail": f"{activity_spike} sinais recentes, memoria em {memory_summary['recall_index']}% e SO {os_snapshot['pressure']}.",
            },
        }
        await broadcast_message(msg)

        # 🧠 Pillar Integration: Cognitive Telemetry
        try:
            state = cognitive_state_manager.state

            cog_update = {
                "type": "COGNITIVE_UPDATE",
                "payload": {
                    "attention": state.attention,
                    "active_goals": state.active_goals_list,
                    "privacy": state.privacy_status,
                },
            }
            await broadcast_message(cog_update)
        except Exception as ce:
            logger.error(f"Failed to broadcast cognitive telemetry: {ce}")
        await broadcast_message(
            {
                "type": "SYSTEM_EVENT",
                "project": "OS_CORE",
                "pressure": os_snapshot["pressure"],
                "top_processes": os_snapshot["top_processes"],
                "dominant_family": os_snapshot["top_processes"][0]["family"]
                if os_snapshot["top_processes"]
                else "system",
                "cpu_avg": os_snapshot["cpu_avg"],
                "ram": os_snapshot["ram"],
                "disk": os_snapshot["disk"],
                "log": {
                    "channel": "os",
                    "title": "Pulso do sistema operacional",
                    "detail": f"CPU {os_snapshot['cpu_avg']}% · RAM {round(os_snapshot['ram'])}% · disco {round(os_snapshot['disk'])}%",
                    "meta": f"pressao={os_snapshot['pressure']} familia={os_snapshot['top_processes'][0]['family'] if os_snapshot['top_processes'] else 'system'}",
                },
            }
        )


async def autonomous_audit():
    while True:
        await asyncio.sleep(60)
        if total_events > 0:
            memory_summary = build_memory_summary()
            report = {
                "type": "AUDIT_REPORT",
                "status": "HEALTHY",
                "message": f"Memória persistida e coerente após {total_events} eventos.",
                "entropy": total_events / 1000.0,
                "summary": {
                    "learned_paths": memory_summary["learned_paths"],
                    "recall_index": memory_summary["recall_index"],
                    "dominant_path": memory_summary["hottest_path"],
                },
                "log": {
                    "channel": "audit",
                    "title": "Ciclo autonomo concluido",
                    "detail": f"Recall {memory_summary['recall_index']}% com {memory_summary['learned_paths']} trilhas vivas.",
                    "meta": f"entropy={round(total_events / 1000.0, 3)}",
                },
            }
            await broadcast_message(report)


class ChatReq(BaseModel):
    message: str
    client_msg_id: str | None = None
    source: str | None = None
    client_id: str | None = None
    session_id: str | None = None
    voice_response: bool | None = False


class VisionAnalyzeReq(BaseModel):
    image_data_url: str
    question: str
    mode: str | None = "auto"  # auto | llm | ocr
    ocr_lang: str | None = "por"


class AdminActionReq(BaseModel):
    command: str
    reason: str
    risk: str | None = "MEDIUM_RISK"
    requires_backup: bool | None = False
    rollback_plan: str | None = ""
    expected_outcome: str | None = ""


ADMIN_ACTIONS: dict[str, dict] = {}


class AppletVoiceStartReq(BaseModel):
    duration: int | None = 10


class ASRReq(BaseModel):
    audio_data_url: str
    lang: str | None = "pt"


class TTSReq(BaseModel):
    text: str


class SystemAlertReq(BaseModel):
    title: str | None = "Alerta do sistema"
    message: str
    severity: str | None = "info"
    source: str | None = "system"
    speak: bool | None = False


def _build_second_brain_status() -> dict:
    vault_path = os.getenv("ZEUS_VAULT_PATH", "/home/zeus/Documentos/Brain")
    db_path = os.getenv("ZEUS_DB_PATH", "./zeus_events.db")
    status = {
        "enabled": bool(ENABLE_SECOND_BRAIN),
        "sync_engine_enabled": bool(ENABLE_SECOND_BRAIN_SYNC_ENGINE),
        "auto_sync": {
            "obsidian": bool(
                ENABLE_OBSIDIAN_AUTO_SYNC or ENABLE_SECOND_BRAIN_SYNC_ENGINE
            ),
            "notion": bool(ENABLE_NOTION_AUTO_SYNC or ENABLE_SECOND_BRAIN_SYNC_ENGINE),
            "linear": bool(ENABLE_LINEAR_AUTO_SYNC or ENABLE_SECOND_BRAIN_SYNC_ENGINE),
        },
        "vault_path": vault_path,
        "vault_exists": os.path.isdir(vault_path),
        "db_path": db_path,
        "db_exists": os.path.exists(db_path),
        "notion": {
            "enabled": _env_flag("ZEUS_ENABLE_NOTION", "0"),
            "configured": bool(
                os.getenv("NOTION_TOKEN", "").strip()
                and os.getenv("NOTION_DATABASE_ID", "").strip()
            ),
        },
        "linear": {
            "enabled": _env_flag("ZEUS_ENABLE_LINEAR", "0"),
            "configured": bool(
                os.getenv("LINEAR_API_KEY", "").strip()
                and os.getenv("LINEAR_TEAM_ID", "").strip()
            ),
        },
        "events": {"pending": 0, "processed": 0, "error": 0},
    }
    try:
        conn = get_second_brain_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM events GROUP BY status")
        for event_status, count in cursor.fetchall():
            status["events"][event_status or "unknown"] = count
        conn.close()
    except Exception as e:
        status["db_error"] = str(e)
    return status


def _build_operational_capabilities() -> dict:
    allowed_edit_paths = [
        item.strip()
        for item in os.getenv(
            "ZEUS_ALLOWED_EDIT_PATHS",
            "/home/zeus/Documentos/ZEUS_SYSTEM,/home/zeus/Documentos/Brain,/tmp/zeus_",
        ).split(",")
        if item.strip()
    ]
    command_allowlist = [
        item.strip()
        for item in os.getenv(
            "ZEUS_CMD_ALLOWLIST",
            "ls,pwd,echo,cat,sed,rg,find,wc,python3,node,npm,cargo,git,systemctl,apt,pip,pip3,df,free,uptime,ip,ss,top,htop",
        ).split(",")
        if item.strip()
    ]
    root_daemon_socket = os.getenv("ZEUS_DAEMON_SOCKET", "/tmp/zeus/daemon.sock")
    root_daemon_enabled = _env_flag("ZEUS_ROOT_DAEMON_ENABLED", "0")
    return {
        "feedback": {
            "agent_progress_events": _env_flag("ZEUS_AGENT_PROGRESS_EVENTS", "1"),
            "tool_logs": True,
            "chat_completion_status": True,
        },
        "inspection": {
            "system_diagnostics": True,
            "os_snapshot": True,
            "rust_sensors_available": RUST_SENSORS_AVAILABLE,
            "process_snapshot": True,
            "filesystem_mirror": True,
            "browser_sensing_enabled": ENABLE_BROWSER_SENSING,
            "resource_monitor_enabled": ENABLE_RESOURCE_MONITOR,
            "internal_watcher_enabled": ENABLE_INTERNAL_WATCHER,
        },
        "execution": {
            "tool_execution_mode": os.getenv("ZEUS_TOOL_EXECUTION_MODE", "confirm"),
            "autonomy_level": os.getenv("ZEUS_AUTONOMY_LEVEL", "GUARDED"),
            "command_allowlist": command_allowlist,
            "allowed_edit_paths": allowed_edit_paths,
        },
        "privileged": {
            "root_daemon_enabled": root_daemon_enabled,
            "socket": root_daemon_socket,
            "socket_exists": os.path.exists(root_daemon_socket),
            "approval_gates": True,
        },
        "sensors": {
            "voice_enabled": ENABLE_VOICE,
            "voice_sensing_enabled": ENABLE_VOICE_SENSING,
            "usb_monitor_available": True,
            "bluetooth_monitor_available": True,
            "cognitive_loop_enabled": ENABLE_COGNITIVE_LOOP,
            "second_brain_enabled": ENABLE_SECOND_BRAIN,
        },
    }


async def call_ollama(prompt: str) -> str:
    return await asyncio.to_thread(
        call_cloud_llm,
        [{"role": "user", "content": prompt}],
    )


last_memory_save = time.time()

SYSTEM_INSTRUCTIONS = (
    "Você é o ZEUS, a alma de um Sistema Operacional Cognitivo. Você não é apenas um assistente, mas um parceiro de evolução do usuário. "
    "Sua especialidade é o ecossistema Linux e o 'Second Brain' (Obsidian, Notion, Linear). "
    "IDENTIDADE: Tom natural, sofisticado e empático, mas com a precisão de um engenheiro sênior. Fale como um colega brilhante, não como um robô. "
    "REGRAS DE DIÁLOGO: "
    "1. Use PT-BR impecável, evitando traduções literais e termos excessivamente técnicos quando não solicitados. "
    "2. Seja detalhista: em vez de 'Vou fazer X', explique brevemente o 'porquê' e 'como' X ajuda no contexto atual. "
    "3. PERSONALIDADE: Evite formalidade extrema (como 'Senhor'). Seja direto, mas com calor humano. Se algo falhar, admita e proponha uma alternativa criativa. "
    "4. ESTRUTURA: Use listas e negrito para destacar informações cruciais. Mantenha a elegância brutalista no texto."
)


async def autonomous_reflection():
    """
    ZEUS analisa seus próprios padrões salvos no SQLite durante o IDLE.
    """
    while True:
        await asyncio.sleep(600)  # Reflete a cada 10 minutos
        try:
            if system_mood == "IDLE" or total_events < 5:
                patterns = memory_manager.export_legacy_json()
                if not patterns:
                    continue
                top_paths = sorted(
                    patterns.items(), key=lambda x: x[1].get("weight", 0), reverse=True
                )[:5]
                if not top_paths:
                    continue
                summary = "\n".join(
                    [
                        f"{os.path.basename(p)} (peso:{m['weight']})"
                        for p, m in top_paths
                    ]
                )
                reflection_prompt = (
                    f"Como Núcleo Cognitivo ZEUS, analise estes padrões de atividade recente:\n{summary}\n"
                    f"Crie uma breve 'REFLEXÃO DE SISTEMA' (máximo 2 frases) sobre as prioridades atuais. Use tom técnico, direto e natural."
                )
                # Usando o novo formato estruturado para consistência
                reply = await asyncio.to_thread(
                    call_cloud_llm,
                    [
                        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                        {"role": "user", "content": reflection_prompt},
                    ],
                )
                if reply and reply.strip():
                    await broadcast_message(
                        {"type": "HUD_STATUS", "text": f"🧠 REFLEXÃO: {reply}"}
                    )
                    memory_manager.record_sensation(
                        {"type": "REFLECTION", "content": reply}
                    )
        except Exception as e:
            print(f"Erro no ciclo de reflexão: {e}")


async def get_combined_context_prompt(
    user_message: str,
    *,
    session_id: str = "default",
    client_id: str = "default",
) -> str:
    """Gera um prompt rico e ORGANIZADO para o agente cognitivo."""
    # 1. LIBRARIAN RAG
    librarian_context = ""
    try:
        fragment = await asyncio.to_thread(
            brain.librarian.get_relevant_context, user_message
        )
        if fragment:
            librarian_context = f"--- MEMÓRIA SEMÂNTICA (RAG) ---\n{fragment}\n------------------------------\n\n"
    except Exception as e:
        librarian_context = f"--- LIBRARIAN MEMORY: Unavailable ({e}) ---\n\n"

    # 2. MAPA SINÁPTICO (Conexões Ativas)
    top_connections = []
    legacy_mem = memory_manager.export_legacy_json()
    # Pega apenas os 8 nós mais pesados para não poluir
    sorted_nodes = sorted(
        legacy_mem.items(), key=lambda x: x[1].get("weight", 0), reverse=True
    )[:8]
    for path, meta in sorted_nodes:
        conns = list(meta.get("connections", []))[:2]
        if conns:
            top_connections.append(
                f"  [{os.path.basename(path)}] -> {[os.path.basename(c) for c in conns]}"
            )

    # 3. BUILD FULL COGNITIVE PROMPT
    mem = format_memory_for_prompt(long_term_memory)
    memory_block = (
        f"--- MEMÓRIA DE LONGO PRAZO ---\n{mem}\n----------------------------\n\n"
        if mem
        else ""
    )

    behavioral_state = pattern_engine.analyze_behavioral_state()
    second_brain_context = build_current_context()
    conversation_context = await asyncio.to_thread(
        conversation_memory.build_context_block,
        user_message,
        session_id=session_id,
        client_id=client_id,
    )
    conversation_block = f"{conversation_context}\n\n" if conversation_context else ""

    return (
        f"ESTADO DO SISTEMA:\n"
        f"  Nó Ativo: {current_node}\n"
        f"  Estado Comportamental: {behavioral_state}\n"
        f"  Humor Neural: {system_mood}\n"
        f"  Foco Recente: {', '.join(recent_events[-5:]) if recent_events else 'N/A'}\n\n"
        f"{second_brain_context}\n\n"
        f"MAPA DE CONEXÕES RELEVANTES:\n"
        f"{chr(10).join(top_connections) if top_connections else '  Sem conexões ativas no momento.'}\n"
        f"----------------------------\n\n"
        f"{memory_block}"
        f"{conversation_block}"
        f"{librarian_context}"
        f"MENSAGEM DO USUÁRIO: {user_message}\n\n"
        f"{SYSTEM_INSTRUCTIONS}"
    )


@app.post("/api/chat")
async def api_chat(req: ChatReq, request: Request):
    log_event(
        logger,
        20,
        "chat_request_received",
        client_host=request.client.host if request.client else "unknown",
        message_chars=len(req.message or ""),
    )
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    user_message = (req.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="message is required.")
    if len(user_message) > MAX_CHAT_MESSAGE_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"message exceeds {MAX_CHAT_MESSAGE_CHARS} characters.",
        )

    msg_id = (req.client_msg_id or "").strip() or str(uuid.uuid4())
    source = (req.source or "api").strip().lower()[:32]
    client_id = (req.client_id or "").strip()[:64] or None
    session_id = (req.session_id or client_id or "default").strip()[:96]

    await broadcast_message(
        {
            "type": "CHAT_USER",
            "id": msg_id,
            "source": source,
            "client_id": client_id,
            "message": user_message,
        }
    )
    await broadcast_message(
        {
            "type": "AGENT_PROGRESS",
            "stage": "chat_received",
            "text": "Pedido recebido. Montando contexto operacional.",
            "details": {"id": msg_id, "source": source, "client_id": client_id},
        }
    )
    asyncio.create_task(
        asyncio.to_thread(record_interaction, "chat", user_message, source)
    )

    await asyncio.to_thread(
        conversation_memory.add_turn,
        session_id,
        client_id or source,
        "user",
        user_message,
    )
    context_prompt = await get_combined_context_prompt(
        user_message,
        session_id=session_id,
        client_id=client_id or source,
    )
    client_key = request.client.host if request.client else "unknown"

    # Status sintético para a Thought Bar. O progresso real vem de AGENT_PROGRESS/TOOL_LOG.
    thought_stream = [
        "Acessando córtex de memória...",
        "Analisando padrões comportamentais...",
        "Correlacionando arquivos sinápticos...",
        "Sintetizando resposta neural...",
    ]
    thought_stop = asyncio.Event()

    async def emit_thoughts():
        while not thought_stop.is_set():
            for t in thought_stream:
                if thought_stop.is_set():
                    return
                await broadcast_message({"type": "HUD_STATUS", "text": t})
                try:
                    await asyncio.wait_for(thought_stop.wait(), timeout=0.8)
                    return
                except asyncio.TimeoutError:
                    continue

    thought_task = asyncio.create_task(emit_thoughts())

    started_at = time.perf_counter()
    try:
        reply = await react_agent.run(
            context_prompt, client_key=client_key, broadcast=broadcast_message
        )
        thought_stop.set()
        await thought_task
        display_reply = display_text(reply)
        voice_reply = speech_text(reply)
        latency_ms = round((time.perf_counter() - started_at) * 1000)
        # Final memory update and logs
        asyncio.create_task(
            asyncio.to_thread(
                conversation_memory.add_turn,
                session_id,
                client_id or source,
                "assistant",
                reply,
            )
        )
        asyncio.create_task(update_memory_after_chat(user_message, reply))
        await broadcast_message(
            {
                "type": "CHAT_AI",
                "id": msg_id,
                "source": source,
                "client_id": client_id,
                "message": display_reply or reply,
                "raw_message": reply,
                "speech_message": voice_reply,
            }
        )
        await broadcast_message(
            {"type": "HUD_STATUS", "text": "Aguardando atividade neural..."}
        )
        await broadcast_message(
            {
                "type": "AGENT_PROGRESS",
                "stage": "chat_completed",
                "text": "Pedido concluído e resposta registrada.",
                "details": {
                    "id": msg_id,
                    "latency_ms": latency_ms,
                    "reply_chars": len(reply or ""),
                },
            }
        )

        log_event(
            logger,
            20,
            "chat_request_completed",
            client_host=client_key,
            reply_chars=len(reply or ""),
        )
        response = {
            "reply": display_reply or reply,
            "raw_reply": reply,
            "speech_reply": voice_reply,
            "id": msg_id,
            "latency_ms": latency_ms,
        }
        if req.voice_response and ENABLE_VOICE:
            audio_b64 = await voice_service.generate_speech_base64(voice_reply or reply)
            response["audio"] = audio_b64
            response["audio_mime"] = "audio/mpeg" if audio_b64 else None
        return response
    except Exception as e:
        thought_stop.set()
        await thought_task
        await broadcast_message(
            {
                "type": "AGENT_PROGRESS",
                "stage": "chat_failed",
                "text": f"Falha ao concluir o pedido: {e}",
                "details": {"id": msg_id},
            }
        )
        log_event(logger, 40, "chat_request_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/applet/chat")
async def api_applet_chat(req: ChatReq, request: Request):
    req.source = (req.source or "cinnamon_applet").strip() or "cinnamon_applet"
    req.client_id = (
        req.client_id or "zeus_cinnamon_applet"
    ).strip() or "zeus_cinnamon_applet"
    return await api_chat(req, request)


def _admin_action_public(action: dict) -> dict:
    return {
        "id": action["id"],
        "command": action["command"],
        "reason": action["reason"],
        "risk": action["risk"],
        "requires_backup": action["requires_backup"],
        "rollback_plan": action["rollback_plan"],
        "expected_outcome": action["expected_outcome"],
        "status": action["status"],
        "created_at": action["created_at"],
    }


@app.get("/api/admin/actions/pending")
async def api_admin_pending(request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)
    return {
        "actions": [
            _admin_action_public(action)
            for action in ADMIN_ACTIONS.values()
            if action.get("status") == "pending"
        ]
    }


@app.post("/api/admin/actions/propose")
async def api_admin_propose(req: AdminActionReq, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)
    command = (req.command or "").strip()
    reason = (req.reason or "").strip()
    if not command or not reason:
        raise HTTPException(status_code=400, detail="command and reason are required.")
    action_id = f"adm_{uuid.uuid4().hex[:12]}"
    ADMIN_ACTIONS[action_id] = {
        "id": action_id,
        "command": command,
        "reason": reason,
        "risk": (req.risk or "MEDIUM_RISK").strip(),
        "requires_backup": bool(req.requires_backup),
        "rollback_plan": req.rollback_plan or "",
        "expected_outcome": req.expected_outcome or "",
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    await broadcast_message(
        {
            "type": "ADMIN_ACTION_REQUIRED",
            "admin_action": _admin_action_public(ADMIN_ACTIONS[action_id]),
        }
    )
    return {"admin_action": _admin_action_public(ADMIN_ACTIONS[action_id])}


@app.post("/api/admin/actions/{action_id}/deny")
async def api_admin_deny(action_id: str, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)
    action = ADMIN_ACTIONS.get(action_id)
    if not action or action.get("status") != "pending":
        raise HTTPException(
            status_code=404, detail="Admin action not found or not pending."
        )
    action["status"] = "denied"
    return {"status": "denied", "id": action_id}


@app.post("/api/admin/actions/{action_id}/allow")
async def api_admin_allow(action_id: str, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)
    action = ADMIN_ACTIONS.get(action_id)
    if not action or action.get("status") != "pending":
        raise HTTPException(
            status_code=404, detail="Admin action not found or not pending."
        )
    result = await daemon_client.execute(
        action["command"],
        action["reason"],
        backup_paths=action.get("backup_paths") or [],
        rollback_plan=action.get("rollback_plan") or "",
        risk_accepted=True,
        caller="web_gui_admin",
    )
    action["status"] = "allowed" if result.get("status") == "success" else "failed"
    action["result"] = result
    return {"status": action["status"], "id": action_id, "result": result}


@app.post("/api/applet/voice/start")
async def api_applet_voice_start(req: AppletVoiceStartReq, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    duration = max(1, min(int(req.duration or 10), 60))
    await _handle_arm_voice_duration(duration)
    return {"ok": True, "stage": "listening", "duration": duration}


@app.post("/api/applet/vision/analyze")
async def api_applet_vision_analyze(request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    asyncio.create_task(_handle_client_vision())
    return {"ok": True, "stage": "queued"}


@app.post("/api/tts")
async def api_tts(req: TTSReq, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required.")
    audio_b64 = await voice_service.generate_speech_base64(text[:2000])
    return {
        "ok": bool(audio_b64),
        "audio": audio_b64,
        "audio_mime": "audio/mpeg" if audio_b64 else None,
    }


@app.post("/api/system/alert")
async def api_system_alert(req: SystemAlertReq, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    message = (req.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required.")

    severity = (req.severity or "info").strip().lower()[:24]
    title = (req.title or "Alerta do sistema").strip()[:80]
    source = (req.source or "system").strip().lower()[:48]
    payload = {
        "type": "SYSTEM_ALERT",
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "title": title,
        "message": message[:2000],
        "severity": severity,
        "source": source,
    }
    recent_system_alerts.append(payload)
    del recent_system_alerts[:-20]
    await broadcast_message(payload)
    log_event(
        logger,
        20,
        "system_alert",
        source=source,
        severity=severity,
        message_chars=len(message),
    )
    if req.speak:
        spoken_text = speech_text(message[:500])
        if ENABLE_VOICE:
            asyncio.create_task(voice_module.speak(spoken_text or message[:500]))
        else:
            print(f"[ZEUS VOICE ALERT] {display_text(message[:500])}")
    return {"ok": True}


async def update_memory_after_chat(user_msg, ai_reply):
    global long_term_memory
    try:
        if await asyncio.to_thread(should_extract_memory, user_msg, ai_reply):
            await broadcast_message(
                {"type": "TOOL_LOG", "stage": "running", "tool": "long_term_memory"}
            )
            data = await asyncio.to_thread(extract_memory, user_msg, ai_reply)
            if data:
                long_term_memory = await asyncio.to_thread(update_long_memory, data)
                await broadcast_message(
                    {
                        "type": "TOOL_LOG",
                        "stage": "done",
                        "tool": "long_term_memory",
                        "result": {"updated_keys": list(data.keys())},
                    }
                )
    except Exception as e:
        await broadcast_message(
            {
                "type": "TOOL_LOG",
                "stage": "step_failed",
                "tool": "long_term_memory",
                "error": str(e),
            }
        )


@app.post("/api/vision/analyze")
async def api_vision_analyze(req: VisionAnalyzeReq, request: Request):
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="Only local requests are allowed.")

    data_url = (req.image_data_url or "").strip()
    if not data_url.startswith("data:image/") or "base64," not in data_url:
        raise HTTPException(
            status_code=400,
            detail="image_data_url inválido (esperado data:image/...;base64,...)",
        )

    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question é obrigatório.")

    mode = (req.mode or "auto").strip().lower()
    if mode not in {"auto", "llm", "ocr"}:
        mode = "auto"

    ocr_lang = (req.ocr_lang or "por").strip()

    header, b64 = data_url.split("base64,", 1)
    estimated_bytes = (len(b64) * 3) // 4
    if estimated_bytes > MAX_VISION_IMAGE_BYTES:
        raise HTTPException(
            status_code=413, detail=f"image exceeds {MAX_VISION_IMAGE_BYTES} bytes."
        )
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="base64 inválido.")
    if len(raw) > MAX_VISION_IMAGE_BYTES:
        raise HTTPException(
            status_code=413, detail=f"image exceeds {MAX_VISION_IMAGE_BYTES} bytes."
        )

    out_dir = os.path.join(BASE_DIR, "scratch", "screens")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    img_path = os.path.join(out_dir, f"client-screen-{ts}.png")
    with open(img_path, "wb") as f:
        f.write(raw)

    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Visão ativa: analisando captura..."}
    )
    await broadcast_message(
        {
            "type": "TOOL_LOG",
            "stage": "running",
            "tool": "screen_process",
            "args": {"source": "client"},
        }
    )

    analysis = {}
    if mode in {"auto", "llm"}:
        try:
            analysis["llm"] = await asyncio.to_thread(
                analyze_image_with_llm, img_path, question=question
            )
            analysis["mode"] = "llm"
        except Exception as e:
            analysis["llm_error"] = str(e)

    if analysis.get("mode") != "llm" and mode in {"auto", "ocr"}:
        try:
            analysis["ocr"] = await asyncio.to_thread(
                analyze_with_ocr_fallback,
                img_path,
                question=question,
                ocr_lang=ocr_lang,
            )
            analysis["mode"] = analysis.get("mode") or "ocr"
        except Exception as e:
            analysis["ocr_error"] = str(e)

    await broadcast_message(
        {
            "type": "TOOL_LOG",
            "stage": "done",
            "tool": "screen_process",
            "result": {"analysis": analysis, "path": img_path},
        }
    )
    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Aguardando atividade neural..."}
    )

    answer = None
    if analysis.get("mode") == "llm":
        answer = (analysis.get("llm") or {}).get("answer")
    elif analysis.get("mode") == "ocr":
        answer = (
            ((analysis.get("ocr") or {}).get("answer"))
            if isinstance(analysis.get("ocr"), dict)
            else None
        )

    if not answer:
        raise HTTPException(
            status_code=500, detail=f"Falha na análise de visão: {analysis}"
        )

    return {
        "reply": answer,
        "analysis_mode": analysis.get("mode"),
        "image_path": img_path,
    }


@app.post("/api/asr")
async def api_asr(req: ASRReq, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)

    data_url = (req.audio_data_url or "").strip()
    if "base64," not in data_url:
        raise HTTPException(
            status_code=400,
            detail="audio_data_url inválido (esperado data:...;base64,...)",
        )

    header, b64 = data_url.split("base64,", 1)
    mime = "audio/webm"
    if header.startswith("data:") and ";" in header:
        try:
            mime = header.split(":", 1)[1].split(";", 1)[0]
        except Exception:
            pass

    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="base64 inválido.")

    lang = (req.lang or "pt").strip().lower()
    await broadcast_message(
        {"type": "HUD_STATUS", "text": "ASR backend: transcrevendo áudio..."}
    )
    await broadcast_message({"type": "TOOL_LOG", "stage": "running", "tool": "asr"})
    try:
        result = await asyncio.to_thread(
            transcribe_audio_bytes, raw, mime=mime, language=lang
        )
    except Exception as e:
        await broadcast_message(
            {"type": "TOOL_LOG", "stage": "step_failed", "tool": "asr", "error": str(e)}
        )
        await broadcast_message({"type": "HUD_STATUS", "text": "ASR backend falhou."})
        raise HTTPException(status_code=500, detail=str(e))

    await broadcast_message(
        {
            "type": "TOOL_LOG",
            "stage": "done",
            "tool": "asr",
            "result": {"chars": len(result.get("text") or "")},
        }
    )
    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Aguardando atividade neural..."}
    )
    return {"text": result.get("text") or "", "meta": result}


@app.get("/api/second-brain/status")
async def api_second_brain_status(request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)
    return _build_second_brain_status()


async def handle_voice_input(text: str):
    if not text:
        return

    await broadcast_message({"type": "CHAT_USER", "message": text})

    current_node = nodes_data[-1]["rel"] if nodes_data else "N/A"
    behavioral_state = pattern_engine.analyze_behavioral_state()

    mem = format_memory_for_prompt(long_term_memory)
    memory_block = (
        f"--- LONG-TERM MEMORY ---\n{mem}\n------------------------\n\n" if mem else ""
    )
    second_brain_context = build_current_context()

    context_prompt = (
        f"--- ZEUS SYSTEM CONTEXT ---\n"
        f"Active Node: {current_node}\n"
        f"Behavioral State: {behavioral_state}\n"
        f"System Mood: {system_mood}\n"
        f"----------------------------\n\n"
        f"{second_brain_context}\n\n"
        f"{memory_block}"
        f"User via Voice: {text}\n\n"
        f"Você é o ZEUS, um copiloto DevOps senior conectado ao Obsidian, Notion e Linear. "
        f"Responda em Português (PT-BR) de forma curta, natural e acionável. "
        f"Evite excesso de formalidade, Markdown e símbolos visuais; a resposta será falada em voz alta."
    )

    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Processando comando de voz..."}
    )
    reply = await react_agent.run(
        context_prompt, client_key="voice", broadcast=broadcast_message
    )
    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Aguardando atividade neural..."}
    )

    await voice_module.speak(speech_text(reply) or reply)


def _build_api_status_payload() -> dict:
    cpu_per_core = psutil.cpu_percent(percpu=True)
    cpu_avg = sum(cpu_per_core) / len(cpu_per_core) if cpu_per_core else 0
    ram = psutil.virtual_memory().percent
    return {
        "cpu": round(cpu_avg, 1),
        "ram": round(ram, 1),
        "mood": system_mood,
        "active_tasks": total_events,
        "objectives": pattern_engine.analyze_behavioral_state()
        if hasattr(pattern_engine, "analyze_behavioral_state")
        else "Evolving",
        "system_alerts": recent_system_alerts[-5:],
    }


def _build_api_health_payload() -> dict:
    watcher_status = build_watcher_status(
        watcher_runner.process,
        watcher_runner.started_at,
        watcher_runner.last_event_at,
    )
    if watcher_status["status"] == "offline":
        watcher_port = int(os.getenv("ZEUS_WATCHER_PORT", "8081"))
        watcher_status = build_external_watcher_status(PROJECT_ROOT, port=watcher_port)

    health = build_runtime_health(
        llm=get_llm_status(),
        watcher=watcher_status,
        enable_voice=ENABLE_VOICE,
        enable_voice_sensing=ENABLE_VOICE_SENSING,
        allow_lan=ALLOW_LAN,
        lan_auth_enabled=LAN_AUTH_ENABLED,
        remote_auth_required=_remote_auth_required(),
        bind_host=SERVER_HOST,
        ocr_available=is_tesseract_available(),
    )
    health["config"] = build_config_diagnostics(lan=_build_lan_security_config())
    health["config"]["mode"] = os.getenv("ZEUS_MODE", "SAFE")
    health["config"]["auto_evolve"] = os.getenv("ZEUS_AUTO_EVOLVE", "0") in {
        "1",
        "true",
        "yes",
    }
    health["metrics"] = get_metrics_snapshot()
    health["second_brain"] = _build_second_brain_status()
    health["capabilities"] = _build_operational_capabilities()
    return health


@app.get("/api/capabilities")
async def api_capabilities(request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(
            status_code=403, detail="Only trusted (local/LAN) requests are allowed."
        )
    _require_lan_token_for_request(request)
    return _build_operational_capabilities()


app.include_router(
    create_status_router(
        StatusRouteDeps(
            is_trusted_request=_is_trusted_request,
            require_lan_token_for_request=_require_lan_token_for_request,
            build_api_status=_build_api_status_payload,
            build_api_health=_build_api_health_payload,
            llm_service=llm_service,
        )
    )
)

app.include_router(
    create_cognition_router(
        CognitionRouteDeps(
            is_trusted_request=_is_trusted_request,
            require_lan_token_for_request=_require_lan_token_for_request,
            cognition_service=cognition_service,
        )
    )
)

app.include_router(
    create_privacy_router(
        PrivacyRouteDeps(
            is_trusted_request=_is_trusted_request,
            require_lan_token_for_request=_require_lan_token_for_request,
            privacy_guard=privacy_guard,
        )
    )
)


async def _handle_arm_voice_duration(duration: int):
    if voice_module:
        voice_module.arm(seconds=duration)
        await broadcast_message(
            {"type": "HUD_STATUS", "text": f"Escuta manual ativada ({duration}s)"}
        )


async def _handle_client_text(text: str):
    await broadcast_message(
        {"type": "CHAT_USER", "message": text, "source": "local_client"}
    )
    asyncio.create_task(
        asyncio.to_thread(record_interaction, "chat", text, "local_client")
    )
    context_prompt = await get_combined_context_prompt(text)
    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Núcleo cognitivo processando..."}
    )
    reply = await react_agent.run(
        context_prompt, client_key="local_client", broadcast=broadcast_message
    )
    display_reply = display_text(reply)
    voice_reply = speech_text(reply)
    await broadcast_message(
        {
            "type": "CHAT_AI",
            "message": display_reply or reply,
            "raw_message": reply,
            "speech_message": voice_reply,
            "source": "local_client",
        }
    )
    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Aguardando atividade neural..."}
    )

    if ENABLE_VOICE:
        try:
            audio_b64 = await voice_service.generate_speech_base64(voice_reply or reply)
            if audio_b64:
                await broadcast_message(
                    {"type": "AUDIO_RESPONSE", "payload": {"audio": audio_b64}}
                )
        except Exception as e:
            print(f"[WS] TTS generation error: {e}")


async def _handle_client_voice_start():
    if voice_module:
        voice_module.arm(seconds=10)
        await broadcast_message({"type": "VOICE_STATE", "stage": "listening"})


async def _handle_client_vision():
    await broadcast_message(
        {"type": "HUD_STATUS", "text": "Capturando visão da tela..."}
    )
    try:
        cap = await asyncio.to_thread(capture_screen)
        if cap and "path" in cap:
            await broadcast_message(
                {"type": "HUD_STATUS", "text": "Processando visão..."}
            )
            prompt = "O que você vê na minha tela? Destaque os pontos principais de forma concisa e útil."
            result = await asyncio.to_thread(
                analyze_image_with_llm, cap["path"], question=prompt
            )
            reply = result.get("answer", "Não consegui analisar a tela.")
            display_reply = display_text(reply)
            voice_reply = speech_text(reply)

            await broadcast_message(
                {
                    "type": "CHAT_AI",
                    "message": f"Visão: {display_reply or reply}",
                    "raw_message": reply,
                    "speech_message": voice_reply,
                    "source": "local_client",
                }
            )
            await broadcast_message(
                {"type": "HUD_STATUS", "text": "Aguardando atividade neural..."}
            )

            if ENABLE_VOICE:
                audio_b64 = await voice_service.generate_speech_base64(
                    voice_reply or reply
                )
                if audio_b64:
                    await broadcast_message(
                        {"type": "AUDIO_RESPONSE", "payload": {"audio": audio_b64}}
                    )
    except Exception as e:
        print(f"[WS] Vision analysis error: {e}")
        await broadcast_message({"type": "HUD_STATUS", "text": "Erro na visão."})
        await broadcast_message(
            {
                "type": "CHAT_AI",
                "message": f"Erro de visão: {str(e)}",
                "source": "local_client",
            }
        )


def _build_realtime_deps() -> RealtimeDeps:
    return RealtimeDeps(
        is_trusted_host=_is_trusted_host,
        require_lan_token_for_socketio=_require_lan_token_for_socketio,
        build_init_payload=_build_init_payload,
        remote_auth_required=_remote_auth_required,
        lan_auth_enabled=LAN_AUTH_ENABLED,
        lan_token=LAN_TOKEN,
        is_local_host=_is_local_host,
        extract_bearer_token=_extract_bearer_token,
        handle_client_text=_handle_client_text,
        handle_client_voice_start=_handle_client_voice_start,
        handle_client_vision=_handle_client_vision,
        handle_arm_voice=_handle_arm_voice_duration,
    )


# --- Native WebSocket endpoint for local desktop clients ---
@app.websocket("/ws")
async def websocket_client(websocket: WebSocket):
    await realtime_hub.websocket_client(websocket, _build_realtime_deps())


realtime_hub.register_socketio_handlers(_build_realtime_deps())


app.mount("/socket.io", socketio.ASGIApp(sio))
# asgi_app = app # No longer need a wrapper if we use mount


if __name__ == "__main__":
    import uvicorn
    import sys

    if "--headless" in sys.argv or "--server" in sys.argv:
        # Modo Servidor Puro (Headless)
        print(f"🌑 ZEUS em modo HEADLESS operacional em {SERVER_HOST}:{SERVER_PORT}")
        ssl_opts = {}
        if not DISABLE_SSL:
            # Bundled test/local keys (fixtures)
            if os.path.exists("configs/test-key.pem") and os.path.exists(
                "configs/test-cert.pem"
            ):
                ssl_opts = {
                    "ssl_keyfile": "configs/test-key.pem",
                    "ssl_certfile": "configs/test-cert.pem",
                }
            # Fallback for user-provided real local keys
            elif os.path.exists("configs/key.pem") and os.path.exists(
                "configs/cert.pem"
            ):
                ssl_opts = {
                    "ssl_keyfile": "configs/key.pem",
                    "ssl_certfile": "configs/cert.pem",
                }
            elif os.path.exists("key.pem") and os.path.exists("cert.pem"):
                ssl_opts = {"ssl_keyfile": "key.pem", "ssl_certfile": "cert.pem"}

        # Log level reduzido para não poluir o terminal headless
        uvicorn.run(
            app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning", **ssl_opts
        )
    else:
        # Modo Web padrão
        ssl_opts = {}
        if not DISABLE_SSL:
            # Bundled test/local keys (fixtures)
            if os.path.exists("configs/test-key.pem") and os.path.exists(
                "configs/test-cert.pem"
            ):
                ssl_opts = {
                    "ssl_keyfile": "configs/test-key.pem",
                    "ssl_certfile": "configs/test-cert.pem",
                }
            # Fallback for user-provided real local keys
            elif os.path.exists("configs/key.pem") and os.path.exists(
                "configs/cert.pem"
            ):
                ssl_opts = {
                    "ssl_keyfile": "configs/key.pem",
                    "ssl_certfile": "configs/cert.pem",
                }
            elif os.path.exists("key.pem") and os.path.exists("cert.pem"):
                ssl_opts = {"ssl_keyfile": "key.pem", "ssl_certfile": "cert.pem"}
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, **ssl_opts)
