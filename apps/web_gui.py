import os
from dotenv import load_dotenv
load_dotenv()

import time
import json
import asyncio
import tempfile
import psutil
import sqlite3
import shutil
import subprocess
import base64
import importlib.util
import ipaddress
import uuid
from pathlib import Path
from collections import Counter
from communication.voice_service import voice_service
from urllib.parse import urlparse
from urllib.parse import parse_qs
PROJECT_ROOT = Path(__file__).resolve().parents[1]
from pattern_engine import PatternEngine
from apps.zeus_evolution import ZeusBrain
from zeus_core.core_system import call_cloud_llm
from zeus_core.agent import Agent
from zeus_core.vector_memory import VectorMemory
from zeus_core.voice_sensing import VoiceSensing
from zeus_core.vision import analyze_image_with_llm, analyze_with_ocr_fallback, is_tesseract_available
from zeus_core.resource_control import ResourceControl
from zeus_core.long_term_memory import (
    extract_memory,
    format_memory_for_prompt,
    load_memory as load_long_memory,
    should_extract_memory,
    update_memory as update_long_memory,
)
from zeus_core.asr import transcribe_audio_bytes
from zeus_core.memory_manager import MemoryManager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import StreamingResponse, RedirectResponse
import socketio

from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import auth
try:
    import firebase_admin  # type: ignore
    from firebase_admin import credentials, messaging  # type: ignore
except Exception:
    firebase_admin = None
    credentials = None
    messaging = None

# --- CONFIGURAÇÕES ---
WATCH_DIRS = [str(PROJECT_ROOT)]
BASE_DIR = str(PROJECT_ROOT)
DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8080",
    "https://127.0.0.1:8080",
    "http://localhost:8080",
    "https://localhost:8080",
]

def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}

ALLOW_LAN = _env_flag("ZEUS_ALLOW_LAN", "0")
DISABLE_SSL = _env_flag("ZEUS_DISABLE_SSL", "0")
print(f"DEBUG: ALLOW_LAN={ALLOW_LAN}, DISABLE_SSL={DISABLE_SSL}")

ENABLE_VOICE = _env_flag("ZEUS_ENABLE_VOICE", "1")
ENABLE_VOICE_SENSING = _env_flag("ZEUS_ENABLE_VOICE_SENSING", "0")
ENABLE_BROWSER_SENSING = _env_flag("ZEUS_ENABLE_BROWSER_SENSING", "0")
ENABLE_OPEN_FILE = _env_flag("ZEUS_ENABLE_OPEN_FILE", "0")
LAN_AUTH_ENABLED = _env_flag("ZEUS_LAN_AUTH", "1" if ALLOW_LAN else "0")
LAN_TOKEN = os.getenv("ZEUS_LAN_TOKEN", "").strip()

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ZEUS_ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS)).split(",")
    if origin.strip()
]
if ALLOW_LAN:
    ALLOWED_ORIGINS = ["*"]

SERVER_HOST = os.getenv("ZEUS_BIND_HOST", "0.0.0.0")
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
SYNAPTIC_PRUNE_INTERVAL_SECONDS = float(os.getenv("ZEUS_SYNAPTIC_PRUNE_INTERVAL_SECONDS", "60") or "60")
EVENT_QUEUE_MAXSIZE = int(os.getenv("ZEUS_EVENT_QUEUE_MAXSIZE", "2000") or "2000")

# Diretórios pesados a serem ignorados completamente
IGNORED_DIRS = {
    ".venv", "__pycache__", ".obsidian", ".git", "node_modules", 
    "target", "dist", ".gemini", ".config", ".cache", "venv",
    ".rustup", ".cargo", ".npm", ".ruff_cache", "build", "zeus_extension",
    "CVS", ".svn", ".idea", ".vscode", "AppData", "Local", "Roaming"
}


def persist_memory_if_needed():
    # Deprecated: memory_manager handles persistence automatically via SQLite.
    pass


# --- STATE ---
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*" if "*" in ALLOWED_ORIGINS else ALLOWED_ORIGINS
)

# Definindo variáveis de estado PRIMEIRO
socketio_clients: set[str] = set()
nodes_data = []
total_events = 0
recent_events_count = 0
system_mood = "CALM"
current_node = "N/A"
recent_events = []
loop = None
event_queue = asyncio.Queue()
_scan_lock = False  # Proteção contra scans simultâneos
MEMORY_FILE = os.path.join(BASE_DIR, "data", "synaptic_memory.json")
memory_manager = MemoryManager(db_path=os.path.join(BASE_DIR, "data", "zeus_memory.db"))
pattern_engine = PatternEngine(MEMORY_FILE)
brain = ZeusBrain() # The Cognitive Core
vector_memory = VectorMemory(storage_file=os.path.join(BASE_DIR, "data", "vector_memory.json"))
memory_manager.vector_memory = vector_memory
voice_module = VoiceSensing(wake_word=os.getenv("ZEUS_WAKE_WORD", "zeus"))
WATCH_ROOTS = [Path(path).resolve() for path in WATCH_DIRS if os.path.exists(path)]
long_term_memory = load_long_memory()
resource_control = ResourceControl(brain.blackboard, {}) # Integrando controle de recursos

# NEW: Message Inbox for Polling clients { client_id: [messages] }
client_inboxes = {}
mobile_clients = set()
mobile_fcm_tokens = {} # { device_id: fcm_token }

# Firebase Initialization
firebase_app = None
if firebase_admin and os.path.exists("configs/serviceAccountKey.json"):
    try:
        cred = credentials.Certificate("configs/serviceAccountKey.json")
        firebase_app = firebase_admin.initialize_app(cred)
        print("🔥 Firebase Admin SDK initialized.")
    except Exception as e:
        print(f"⚠️ Firebase Init Error: {e}")

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
    
    # Start the Rust watcher as a background task
    asyncio.create_task(run_rust_watcher())
    
    # Monitorar navegações web apenas com opt-in explícito
    global _web_sensing_task
    if ENABLE_BROWSER_SENSING:
        _web_sensing_task = asyncio.create_task(web_sensing_loop())
    
    # Inicia o batcher e tarefas proativas
    asyncio.create_task(event_batcher())
    asyncio.create_task(autonomous_audit())
    
    asyncio.create_task(metrics_loop())
    asyncio.create_task(resource_control.monitor_and_report()) # Inicia telemetria de recursos
    
    # Inicia o Sensing de Voz (apenas se disponível e habilitado)
    global _voice_task
    if ENABLE_VOICE and ENABLE_VOICE_SENSING:
        _voice_task = asyncio.create_task(_safe_voice_task())
    
    # NEW: Reflexão Cognitiva Autônoma
    asyncio.create_task(autonomous_reflection())

    # Guardião de low-mem (desativa features pesadas automaticamente)
    if LOW_MEM_AUTO:
        asyncio.create_task(low_mem_guard())
    
    # Saudação inicial com a cognição
    asyncio.create_task(boot_greeting())
    
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

app = FastAPI(lifespan=lifespan)


async def send_push_notification(title: str, body: str, data: dict = None):
    if not firebase_app:
        return
    
    messages = []
    for token in mobile_fcm_tokens.values():
        messages.append(messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
        ))
    
    if messages:
        try:
            response = messaging.send_all(messages)
            print(f"🔔 Push sent: {response.success_count} success")
        except Exception as e:
            print(f"⚠️ Push Error: {e}")

class LoginRequest(BaseModel):
    token: str # Por enquanto usaremos o ZEUS_MOBILE_TOKEN como "senha"

@app.post("/api/mobile/login")
async def mobile_login(req: LoginRequest, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(status_code=403, detail="Only trusted (local/LAN) requests are allowed.")
    _require_lan_token_for_request(request)
    if req.token == ZEUS_MOBILE_TOKEN:
        access_token = auth.create_access_token(data={"sub": "zeus_mobile_extension"})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid ZEUS Token")

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

# Reconfigura a fila com limite (reduz risco de RAM explodir em bursts do watcher)
if EVENT_QUEUE_MAXSIZE and EVENT_QUEUE_MAXSIZE > 0:
    event_queue = asyncio.Queue(maxsize=EVENT_QUEUE_MAXSIZE)


async def enqueue_event(event: dict) -> None:
    """
    Enfileira eventos com política de overflow: descarta o mais antigo.
    Isso evita crescimento ilimitado de RAM em bursts.
    """
    try:
        event_queue.put_nowait(event)
        return
    except asyncio.QueueFull:
        pass
    except Exception:
        return

    # Fila cheia: tenta descartar 1 e inserir de novo.
    try:
        event_queue.get_nowait()
    except Exception:
        return
    try:
        event_queue.put_nowait(event)
    except Exception:
        return

# Android Mobile State
mobile_clients = set()
ZEUS_MOBILE_TOKEN = os.getenv("ZEUS_MOBILE_TOKEN", "zeus_secure_123")


async def speak(text, target: str = "all"):
    """Toca TTS local (Edge-TTS + ffplay) via VoiceSensing quando habilitado e avisa clientes mobile."""
    if not text or not text.strip():
        return
    try:
        if not ENABLE_VOICE:
            # Em modo somente texto, não enviamos o comando de voz nem para mobile
            print(f"[ZEUS VOICE ALERT] {text}")
            return

        # Sempre envia o comando de voz para App/Web.
        # Assim, o mobile continua falando mesmo que o TTS local do servidor esteja desabilitado.
        await broadcast_message({
            "type": "voice_play",
            "text": text,
            "voice": "pt-BR-AntonioNeural",
            "target": target,
        })

        # Mantém a fala no servidor quando habilitado
        await voice_module.speak(text)
    except Exception as e:
        print(f"[ZEUS] Falha ao falar (fallback para log): {e}")
        print(f"[ZEUS VOICE ALERT] {text}")

async def cleanup_voice_temp_files():
    pass


def _is_local_request(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    return client.host in {"127.0.0.1", "::1", "localhost"}

def _is_trusted_host(host: str | None) -> bool:
    if not host:
        return False
    if host in {"127.0.0.1", "::1", "localhost"}:
        return True
    trusted = {h.strip() for h in os.getenv("ZEUS_TRUSTED_IPS", "").split(",") if h.strip()}
    if host in trusted:
        return True
    if ALLOW_LAN:
        return True # Permite qualquer host se LAN estiver habilitada
    try:
        ip = ipaddress.ip_address(host)
    except Exception:
        return False
    return bool(ip.is_private or ip.is_loopback)

def _is_trusted_request(request: Request) -> bool:
    client = request.client
    return _is_trusted_host(client.host if client else None)

def _is_local_host(host: str | None) -> bool:
    return bool(host and host in {"127.0.0.1", "::1", "localhost"})

def _extract_bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.lower().startswith("bearer "):
        return value.split(" ", 1)[1].strip() or None
    return value

def _require_lan_token_for_request(request: Request) -> None:
    """
    Quando ZEUS_ALLOW_LAN=1, exige token para chamadas vindas de hosts não-locais.
    Objetivo: evitar que qualquer device na LAN tenha acesso ao core.
    """
    if not (ALLOW_LAN and LAN_AUTH_ENABLED):
        return
    client = request.client
    host = client.host if client else None
    if _is_local_host(host):
        return
    if not LAN_TOKEN:
        raise HTTPException(status_code=500, detail="LAN token not configured on server.")
    header_token = _extract_bearer_token(request.headers.get("authorization"))
    header_token = header_token or _extract_bearer_token(request.headers.get("x-zeus-token"))
    query_token = _extract_bearer_token(request.query_params.get("token"))
    if (header_token or query_token) != LAN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing ZEUS LAN token.")

def _require_lan_token_for_socketio(environ: dict, auth_payload: dict | None) -> bool:
    if not (ALLOW_LAN and LAN_AUTH_ENABLED):
        return True
    host = None
    try:
        host = environ.get("REMOTE_ADDR")
    except Exception:
        host = None
    if not host:
        try:
            scope = environ.get("asgi.scope") or {}
            client = scope.get("client")
            host = client[0] if isinstance(client, (list, tuple)) and client else None
        except Exception:
            host = None
    if _is_local_host(host):
        return True
    if not LAN_TOKEN:
        return False
    provided = None
    if isinstance(auth_payload, dict):
        provided = _extract_bearer_token(auth_payload.get("token"))
    if not provided:
        qs = environ.get("QUERY_STRING") or ""
        try:
            parsed = parse_qs(qs)
            provided = _extract_bearer_token((parsed.get("token") or [None])[0])
        except Exception:
            provided = None
    if not provided:
        provided = _extract_bearer_token(environ.get("HTTP_X_ZEUS_TOKEN")) or _extract_bearer_token(environ.get("HTTP_AUTHORIZATION"))
    return provided == LAN_TOKEN

def _validate_lan_security_config() -> None:
    if not (ALLOW_LAN and LAN_AUTH_ENABLED):
        return
    if not LAN_TOKEN or len(LAN_TOKEN) < 16:
        raise RuntimeError("ZEUS_LAN_TOKEN must be set (>=16 chars) when ZEUS_ALLOW_LAN=1 and ZEUS_LAN_AUTH=1.")
    jwt_secret = os.getenv("ZEUS_JWT_SECRET", "").strip()
    if not jwt_secret or jwt_secret == "super_secret_zeus_key_998877":
        raise RuntimeError("ZEUS_JWT_SECRET must be set (avoid default) when ZEUS_ALLOW_LAN=1 and ZEUS_LAN_AUTH=1.")
    mobile_token = os.getenv("ZEUS_MOBILE_TOKEN", "").strip()
    if not mobile_token or mobile_token == "zeus_secure_123":
        raise RuntimeError("ZEUS_MOBILE_TOKEN must be set (avoid default) when ZEUS_ALLOW_LAN=1 and ZEUS_LAN_AUTH=1.")


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
                with tempfile.NamedTemporaryFile(prefix="zeus_web_history_", delete=False) as temp_file:
                    temp_history = temp_file.name
                shutil.copy2(path, temp_history)
                conn = sqlite3.connect(temp_history)
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM urls ORDER BY last_visit_time DESC LIMIT 1")
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
    elif any(token in domain for token in ["youtube", "x.com", "twitter", "reddit", "news"]):
        category = "media"
    elif any(token in domain for token in ["google", "duckduckgo", "bing"]):
        category = "search"
    return {
        "domain": domain or "unknown",
        "category": category,
        "path": parsed.path or "/",
    }


def get_os_snapshot():
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
                if cpu < 1.0 and mem < 1.0: # Ignora processos irrelevantes
                    continue
                process_rows.append({
                    "name": info.get("name") or "unknown",
                    "cpu": round(cpu, 1),
                    "memory": round(mem, 1),
                    "family": classify_process_family(info.get("name") or "unknown"),
                })
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
    if any(token in normalized for token in ["python", "node", "bun", "cargo", "rust", "java"]):
        return "runtime"
    if any(token in normalized for token in ["docker", "podman", "qemu", "vm"]):
        return "infra"
    if any(token in normalized for token in ["pipewire", "pulseaudio", "wireplumber", "spotify", "vlc"]):
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
    
    # Record sensation in L1
    memory_manager.record_sensation(event)
    
    # Update synapse/node in L2
    memory_manager.update_synapse(path, path) # Self-update weight

    if event["event"] == "SCAN" or event["event"] == "Create":
        # Get weight from L2
        conn = sqlite3.connect(memory_manager.db_path)
        c = conn.cursor()
        c.execute('SELECT weight FROM nodes WHERE path = ?', (path,))
        row = c.fetchone()
        weight = row[0] if row else 1
        conn.close()

        nodes_data.append({
            "rel": path,
            "name": os.path.basename(path),
            "project": event["project"],
            "color": get_project_color(event["project"]),
            "weight": weight,
            "cluster": get_node_cluster(path)
        })
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
                print(f"[ZEUS RESOURCE ALERT] High pressure detected. Indexing paused for {path}...")
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
    if any(ext in path_lower for ext in [".py", ".rs", ".js", ".ts", ".tsx", ".html", ".css", ".md"]):
        return "files"
    if "http" in path_lower or "www" in path_lower:
        return "web"
    if any(token in path_lower for token in ["bin", "etc", "var", "system", "kernel", "proc"]):
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
    
    cursor.execute('SELECT COUNT(*) FROM nodes')
    learned_paths = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(weight) FROM synapses')
    connection_total = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT path, weight FROM nodes ORDER BY weight DESC LIMIT 1')
    row = cursor.fetchone()
    hottest_path, hottest_weight = row if row else (None, 0)
    
    conn.close()

    recall_index = min(100, round((connection_total * 2 + hottest_weight) / max(1, learned_paths)))
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
    code_hits = sum(1 for path in paths if path.endswith((".py", ".rs", ".js", ".ts", ".tsx", ".jsx", ".html", ".css")))
    return {
        "event_count": len(file_events),
        "dominant_project": dominant_project,
        "dominant_kind": dominant_kind,
        "markdown_hits": markdown_hits,
        "code_hits": code_hits,
        "sample_paths": paths[:WS_BATCH_SAMPLE_LIMIT],
    }


def resolve_watcher_binary():
    candidates = [
        Path(BASE_DIR) / "watcher_rs" / "target" / "release" / "watcher_rs",
        Path(BASE_DIR) / "watcher_rs" / "target" / "debug" / "watcher_rs",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


async def log_subprocess_stream(stream, label):
    while True:
        line = await stream.readline()
        if not line:
            break
        print(f"[{label}] {line.decode(errors='ignore').rstrip()}")

async def run_rust_watcher():
    """Executes the Rust watcher and forwards events to the event_queue."""
    binary_path = resolve_watcher_binary()
    if not binary_path:
        print("Rust watcher binary not found. Build watcher_rs before starting the GUI.")
        return

    process = await asyncio.create_subprocess_exec(
        binary_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stderr_task = asyncio.create_task(log_subprocess_stream(process.stderr, "watcher_rs"))
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        try:
            data = json.loads(line.decode())
            event = {
                "type": "FILE_EVENT",
                "event": data["event_type"],
                "path": data["path"],
                "project": data["project"],
            }
            await enqueue_event(event)
        except Exception as e:
            print(f"Error parsing Rust output: {e}")
    await stderr_task

_voice_task_running = False

async def _safe_voice_task():
    """Inicia o módulo de voz local contínuo com proteção contra múltiplas instâncias."""
    global _voice_task_running
    try:
        voice_module.broadcast = broadcast_message
        voice_module.llm_callback = handle_voice_input
        
        while True:
            if not ENABLE_VOICE or LOW_MEM_ACTIVE:
                if voice_module.is_listening:
                    voice_module.stop()
                    _voice_task_running = False
                await asyncio.sleep(5.0)
                continue
            if resource_control.is_critical():
                if voice_module.is_listening:
                    print("[ZEUS RESOURCE ALERT] Critical Load. Pausing Voice Sensing...")
                    voice_module.stop()
                    _voice_task_running = False
                await asyncio.sleep(10.0)
                continue
            
            if not voice_module.is_listening and not _voice_task_running:
                _voice_task_running = True
                print("[ZEUS] Iniciando módulo de voz local...")
                asyncio.create_task(voice_module.run())
            
            await asyncio.sleep(5.0) # Check every 5s
    except Exception as e:
        print(f"Erro crítico no _safe_voice_task: {e}")
        _voice_task_running = False


async def low_mem_guard():
    """
    Modo low-mem automático:
    - Desativa Voz e Web Sensing em alta pressão de RAM
    - Reduz concorrência de indexação e força poda de memória
    """
    global ENABLE_VOICE, ENABLE_BROWSER_SENSING, LOW_MEM_ACTIVE, indexing_semaphore, _web_sensing_task

    while True:
        try:
            snapshot = resource_control.get_system_snapshot()
            ram = float(snapshot.get("ram", 0.0))
        except Exception:
            ram = 0.0

        if not LOW_MEM_ACTIVE and ram >= LOW_MEM_ENTER_RAM:
            LOW_MEM_ACTIVE = True
            print(f"[ZEUS LOW-MEM] Entering low-mem mode (RAM={ram}%).")

            # Desativa voz (pesado: Whisper/TTS)
            ENABLE_VOICE = False
            try:
                if voice_module.is_listening:
                    voice_module.stop()
            except Exception:
                pass

            # Desativa web sensing (evita loops e automações)
            ENABLE_BROWSER_SENSING = False
            try:
                if _web_sensing_task:
                    _web_sensing_task.cancel()
                    _web_sensing_task = None
            except Exception:
                pass

            # Reduz indexação concorrente
            try:
                indexing_semaphore = asyncio.Semaphore(1)
            except Exception:
                pass

            # Poda agressiva para reduzir RAM
            try:
                prune_synaptic_memory(force=True)
            except Exception:
                pass

        elif LOW_MEM_ACTIVE and ram <= LOW_MEM_EXIT_RAM:
            LOW_MEM_ACTIVE = False
            print(f"[ZEUS LOW-MEM] Exiting low-mem mode (RAM={ram}%).")

            # Reabilita se o usuário tiver habilitado via env na inicialização
            # (não ligamos automaticamente se estava desligado por configuração)
            if _env_flag("ZEUS_ENABLE_VOICE", "1"):
                ENABLE_VOICE = True
            if _env_flag("ZEUS_ENABLE_BROWSER_SENSING", "0"):
                ENABLE_BROWSER_SENSING = True
                if _web_sensing_task is None:
                    try:
                        _web_sensing_task = asyncio.create_task(web_sensing_loop())
                    except Exception:
                        pass

            # Retorna concorrência padrão
            try:
                indexing_semaphore = asyncio.Semaphore(2)
            except Exception:
                pass

        await asyncio.sleep(3.0)

# Update lifespan to use the Rust watcher instead of BrainWatcher
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOW_LAN else ALLOWED_ORIGINS,
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
            raise HTTPException(status_code=400, detail="Path is outside allowed watch roots.")
        if not ENABLE_OPEN_FILE:
            raise HTTPException(status_code=403, detail="Open-file integration is disabled.")
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
        await broadcast_message({
            "type": "AI_INSIGHT",
            "message": insight,
            "mood": system_mood
        })
        
    return {"insight": insight}


@app.post("/api/web-context")
async def receive_web_context(data: dict, request: Request):
    """
    Recebe contexto de extensões de navegador (URL, Título, Seleção de texto).
    """
    url = data.get("url")
    title = data.get("title")
    content = data.get("content") or ""
    
    if not url:
        return {"status": "error", "message": "No URL provided"}

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

    await broadcast_message({
        "type": "WEB_EVENT",
        "url": url,
        "title": title,
        "log": {
            "channel": "web",
            "title": "Consciência Web Expandida",
            "detail": f"ZEUS assimilou conteúdo de: {title or url}",
            "meta": f"length={len(content)}"
        }
    })
    
    return {"status": "success"}


@app.get("/status")
async def get_status(request: Request):
    _require_lan_token_for_request(request)
    client_id = request.headers.get("x-zeus-client-id")
    
    cpu_per_core = psutil.cpu_percent(percpu=True)
    cpu_avg = sum(cpu_per_core) / len(cpu_per_core) if cpu_per_core else 0
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    
    # Collect pending messages for this client
    pending_msgs = []
    if client_id and client_id in client_inboxes:
        pending_msgs = client_inboxes[client_id][:]
        client_inboxes[client_id] = [] # Clear after delivery
    
    return {
        "cpu": cpu_per_core,
        "ram": ram,
        "disk": disk,
        "total_events": total_events,
        "mood": system_mood,
        "active_path": nodes_data[-1]["rel"] if nodes_data else "ZEUS_SYSTEM / IDLE",
        "project_activity": build_project_activity(),
        "messages": pending_msgs
    }

@sio.on('connect')
async def handle_connect(sid, environ, auth_payload=None):
    host = None
    try:
        host = environ.get("REMOTE_ADDR")
    except Exception:
        host = None
    if not host:
        try:
            scope = environ.get("asgi.scope") or {}
            client = scope.get("client")
            host = client[0] if isinstance(client, (list, tuple)) and client else None
        except Exception:
            host = None
    if not _is_trusted_host(host):
        print(f"[Socket.io] REJECTED connect from untrusted host: {host}")
        return False
    if not _require_lan_token_for_socketio(environ, auth_payload):
        print(f"[Socket.io] REJECTED connect (invalid/missing token) host={host}")
        return False
    socketio_clients.add(sid)
    print(f"[Socket.io] Client connected: {sid}")
    try:
        await sio.emit("message", _build_init_payload(), to=sid)
    except Exception as e:
        print(f"[Socket.io] Failed to send init payload to {sid}: {e}")

@sio.on('disconnect')
async def handle_disconnect(sid):
    socketio_clients.discard(sid)
    print(f"[Socket.io] Client disconnected: {sid}")

@sio.on('audio_stream')
async def handle_audio_stream(sid, data):
    """
    Recebe chunks de áudio base64 de clientes móveis/web.
    Preparação para o modo Walkie-Talkie (Voz Duplex).
    """
    try:
        # data expected to be a dict: {"audio": "base64_string..."}
        if isinstance(data, dict) and "audio" in data:
            chunk = data["audio"]
            # Por enquanto, apenas logamos o recebimento pacífico para não travar o loop
            # Futuramente isso irá para um buffer de transcrição nativa (Whisper/Vosk).
            print(f"[Socket.io] Received audio chunk from {sid} (size: {len(chunk)} bytes)")
        else:
            print(f"[Socket.io] Invalid audio stream payload from {sid}")
    except Exception as e:
        print(f"[Socket.io] Error processing audio stream: {e}")

async def broadcast_message(msg: dict):
    """Envio massivo via Socket.io e WebSocket nativo mobile."""
    try:
        await sio.emit("message", msg)
        
        # NEW: Critical alerts also trigger Push Notification
        if msg.get("type") == "alert" and msg.get("level") == "critical":
            await send_push_notification("⚠️ ZEUS CRITICAL", msg.get("message", "Alerta crítico do sistema"))

        dead_clients = set()
        for client in mobile_clients:
            try:
                # Use send_text with ensure_ascii=False to fix accent issues on mobile
                await client.send_text(json.dumps(msg, ensure_ascii=False))
            except Exception:
                dead_clients.add(client)
        for c in dead_clients:
            mobile_clients.discard(c)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f" [BROADCAST ERROR] {e} | MSG: {str(msg)[:200]}")
    
    if "client_id" in msg:
        cid = msg["client_id"]
        if cid not in client_inboxes:
            client_inboxes[cid] = []
        client_inboxes[cid].append(msg)
        if len(client_inboxes[cid]) > 20:
            client_inboxes[cid].pop(0)
    else:
        for cid in client_inboxes:
            client_inboxes[cid].append(msg)
            if len(client_inboxes[cid]) > 20:
                client_inboxes[cid].pop(0)

async def voice_context_trigger(text: str, channel: str = "system"):

    """Gera um alerta de voz contextualizado."""
    if not ENABLE_VOICE or not text or not text.strip():
        return
    
    prefix = {
        "cognitive": "Sussurro cerebral: ",
        "signal": "Sinal detectado: ",
        "os": "Alerta de sistema: ",
        "system": "ZEUS informa: "
    }.get(channel, "")
    
    full_text = f"{prefix}{text}"
    await speak(full_text)

async def web_sensing_loop():
    """Monitora navegações web e injeta como eventos na rede neural."""
    while True:
        await asyncio.sleep(5.0)
        url = get_browser_history()
        if url:
            web_context = classify_web_context(url)
            event = {
                "type": "FILE_EVENT",
                "event": "WEB_VISIT",
                "path": url,
                "project": "WEB_SENSING",
            }
            await enqueue_event(event)
            await broadcast_message({
                "type": "WEB_EVENT", 
                "url": url, 
                "project": "WEB_SENSING"
                ,
                "domain": web_context["domain"],
                "category": web_context["category"],
                "path_hint": web_context["path"],
                "log": {
                    "channel": "web",
                    "title": "Navegação detectada",
                    "detail": f"{web_context['domain']} entrou no radar.",
                    "meta": f"categoria={web_context['category']}",
                }
            })

async def event_batcher():
    global total_events, recent_events_count
    while True:
        events = []
        first_event = await event_queue.get()
        is_scan_burst = first_event.get("event") == "SCAN"
        batch_window = SCAN_BATCH_WINDOW if is_scan_burst else EVENT_BATCH_WINDOW

        if "type" in first_event and first_event["type"] == "FILE_EVENT":
            await update_nodes_on_event(first_event)
            total_events += 1
            recent_events_count += 1
            
        events.append(first_event)
        pulse_first = pattern_engine.process_event(first_event)

        await asyncio.sleep(batch_window)
        while not event_queue.empty() and len(events) < MAX_BATCH_EVENTS:
            ev = event_queue.get_nowait()

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
                "memory": "Memória (sinapse) consolidando"
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
                await broadcast_message({
                    "type": "FILE_EVENT_BATCH",
                    "mode": "scan",
                    "event_count": len(events),
                    "projects": sorted({e.get("project", "unknown") for e in events}),
                    "sample_paths": [e.get("path") for e in events[:WS_BATCH_SAMPLE_LIMIT] if e.get("path")],
                    "signal_profile": batch_summary,
                    "memory_summary": memory_summary,
                    "active_cluster": dominant_cluster,
                    "log": {
                        "channel": "memory",
                        "title": "Scan assimilado",
                        "detail": cluster_logs.get(dominant_cluster, f"{batch_summary['event_count']} sinais incorporados."),
                        "meta": f"kind={batch_summary['dominant_kind']} md={batch_summary['markdown_hits']} code={batch_summary['code_hits']}",
                    },
                })
            elif len(events) > 1:
                await broadcast_message(pulse_first)
                await broadcast_message({
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
                        "detail": cluster_logs.get(dominant_cluster, f"{batch_summary['event_count']} eventos sincronizados."),
                        "meta": f"kind={batch_summary['dominant_kind']} code={batch_summary['code_hits']}",
                    },
                })
                
                # Proatividade: Sugerir arquivos semanticamente próximos do arquivo mais recente
                suggestions = []
                last_path = paths[-1] if paths else None
                if last_path:
                    # Use find_similar_by_key to search by existing vector instead of path text
                    similar = await asyncio.to_thread(vector_memory.find_similar_by_key, last_path, 2)
                    if similar:
                        suggestions = [p for p, s in similar if p != last_path]
                if suggestions:
                    await broadcast_message({
                        "type": "PROACTIVE_SENSING",
                        "target": last_path,
                        "suggestions": suggestions,
                        "log": {
                            "channel": "cognitive",
                            "title": "Sussurro Semântico",
                            "detail": f"Detectei correlação profunda com {os.path.basename(suggestions[0])}.",
                            "meta": "vector_match=high"
                        }
                    })
                    await voice_context_trigger(f"Detectei correlação profunda com {os.path.basename(suggestions[0])}", "cognitive")

            else:
                await broadcast_message(pulse_first)
                await broadcast_message({
                    **events[0],
                    "active_cluster": dominant_cluster,
                    "log": {
                        "channel": "signal",
                        "title": "Sinal isolado",
                        "detail": cluster_logs.get(dominant_cluster, "Sinal processado."),
                        "meta": f"cluster={dominant_cluster}"
                    }
                })



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
                "save_age_seconds": round(time.time() - last_memory_save, 1) if last_memory_save else None,
            },
            "os_context": os_snapshot,
            "system_update": {
                "headline": f"Estado {behavioral_state.lower()}",
                "detail": f"{activity_spike} sinais recentes, memoria em {memory_summary['recall_index']}% e SO {os_snapshot['pressure']}.",
            }
        }
        await broadcast_message(msg)
        await broadcast_message({
            "type": "SYSTEM_EVENT",
            "project": "OS_CORE",
            "pressure": os_snapshot["pressure"],
            "top_processes": os_snapshot["top_processes"],
            "dominant_family": os_snapshot["top_processes"][0]["family"] if os_snapshot["top_processes"] else "system",
            "cpu_avg": os_snapshot["cpu_avg"],
            "ram": os_snapshot["ram"],
            "disk": os_snapshot["disk"],
            "log": {
                "channel": "os",
                "title": "Pulso do sistema operacional",
                "detail": f"CPU {os_snapshot['cpu_avg']}% · RAM {round(os_snapshot['ram'])}% · disco {round(os_snapshot['disk'])}%",
                "meta": f"pressao={os_snapshot['pressure']} familia={os_snapshot['top_processes'][0]['family'] if os_snapshot['top_processes'] else 'system'}",
            },
        })


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


class VisionAnalyzeReq(BaseModel):
    image_data_url: str
    question: str
    mode: str | None = "auto"  # auto | llm | ocr
    ocr_lang: str | None = "por"


class ASRReq(BaseModel):
    audio_data_url: str
    lang: str | None = "pt"

async def call_ollama(prompt: str) -> str:
    return await asyncio.to_thread(
        call_cloud_llm,
        [{"role": "user", "content": prompt}],
    )

last_memory_save = time.time()

SYSTEM_INSTRUCTIONS = (
    "Você é o ZEUS, um Sistema Operacional Cognitivo de última geração baseado em Gemini 3 Flash. "
    "Sua personalidade é imponente, técnica, onisciente e extremamente educada. "
    "Você deve ser formal, preciso e elegante em suas respostas. "
    "Você tem acesso total ao sistema de arquivos e ferramentas através do ReAct. "
    "Aja como uma inteligência superior que auxilia o usuário com precisão absoluta."
)

async def boot_greeting():
    try:
        # Dá um tempinho para o servidor FastAPI subir completamente
        await asyncio.sleep(3)
        prompt = "O sistema ZEUS (Núcleo Gemini 3) acaba de ser iniciado. Crie uma mensagem falada muito curta de boas-vindas (máximo 1 frase), chamando o usuário de 'Senhor'. Seja imponente, técnico e direto."
        reply = await call_ollama(prompt)
        if reply and reply.strip():
            await speak(reply)
        else:
            await speak("Olá, Senhor. O sistema ZEUS Gemini 3 está online.")
    except Exception as e:
        print(f"Erro na saudação inicial: {e}")
        await speak("Olá, Senhor. O sistema ZEUS está online.")
async def autonomous_reflection():
    """
    ZEUS analisa seus próprios padrões salvos no SQLite durante o IDLE.
    """
    while True:
        await asyncio.sleep(600) # Reflete a cada 10 minutos
        try:
            if system_mood == "IDLE" or total_events < 5:
                patterns = memory_manager.export_legacy_json()
                if not patterns: continue
                top_paths = sorted(patterns.items(), key=lambda x: x[1].get('weight', 0), reverse=True)[:5]
                if not top_paths: continue
                summary = "\n".join([f"{os.path.basename(p)} (peso:{m['weight']})" for p, m in top_paths])
                reflection_prompt = (
                    f"Como Núcleo Cognitivo ZEUS (Powered by Gemini 3), analise estes padrões de atividade recente:\n{summary}\n"
                    f"Crie uma breve 'REFLEXÃO DE SISTEMA' (máximo 2 frases) sobre as prioridades atuais do Senhor. Use tom imponente, técnico e onisciente."
                )
                # Usando o novo formato estruturado para consistência
                reply = await call_cloud_llm([
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": reflection_prompt}
                ])
                if reply and reply.strip():
                    await broadcast_message({"type": "HUD_STATUS", "text": f"🧠 REFLEXÃO: {reply}"})
                    memory_manager.record_sensation({"type": "REFLECTION", "content": reply})
        except Exception as e:
            print(f"Erro no ciclo de reflexão: {e}")


async def get_combined_context_prompt(user_message: str) -> str:
    """Gera um prompt rico e ORGANIZADO para o agente cognitivo."""
    # 1. LIBRARIAN RAG
    librarian_context = ""
    try:
        fragment = await asyncio.to_thread(brain.librarian.get_relevant_context, user_message)
        if fragment:
            librarian_context = f"--- MEMÓRIA SEMÂNTICA (RAG) ---\n{fragment}\n------------------------------\n\n"
    except Exception as e:
        librarian_context = f"--- LIBRARIAN MEMORY: Unavailable ({e}) ---\n\n"

    # 2. MAPA SINÁPTICO (Conexões Ativas)
    top_connections = []
    legacy_mem = memory_manager.export_legacy_json()
    # Pega apenas os 8 nós mais pesados para não poluir
    sorted_nodes = sorted(legacy_mem.items(), key=lambda x: x[1].get('weight', 0), reverse=True)[:8]
    for path, meta in sorted_nodes:
        conns = list(meta.get("connections", []))[:2]
        if conns:
            top_connections.append(f"  [{os.path.basename(path)}] -> {[os.path.basename(c) for c in conns]}")

    # 3. BUILD FULL COGNITIVE PROMPT
    mem = format_memory_for_prompt(long_term_memory)
    memory_block = f"--- MEMÓRIA DE LONGO PRAZO ---\n{mem}\n----------------------------\n\n" if mem else ""
    
    behavioral_state = pattern_engine.analyze_behavioral_state()
    
    return (
        f"ESTADO DO SISTEMA:\n"
        f"  Nó Ativo: {current_node}\n"
        f"  Estado Comportamental: {behavioral_state}\n"
        f"  Humor Neural: {system_mood}\n"
        f"  Foco Recente: {', '.join(recent_events[-5:]) if recent_events else 'N/A'}\n\n"
        f"MAPA DE CONEXÕES RELEVANTES:\n"
        f"{chr(10).join(top_connections) if top_connections else '  Sem conexões ativas no momento.'}\n"
        f"----------------------------\n\n"
        f"{memory_block}"
        f"{librarian_context}"
        f"MENSAGEM DO USUÁRIO: {user_message}\n\n"
        f"{SYSTEM_INSTRUCTIONS}"
    )


@app.post("/api/chat")
async def api_chat(req: ChatReq, request: Request):
    print(f"\n[DEBUG CHAT] Incoming request from {request.client.host}: {req.message}")
    if not _is_trusted_request(request):
        raise HTTPException(status_code=403, detail="Only trusted (local/LAN) requests are allowed.")
    _require_lan_token_for_request(request)
    
    msg_id = (req.client_msg_id or "").strip() or str(uuid.uuid4())
    source = (req.source or "api").strip().lower()[:32]
    client_id = (req.client_id or "").strip()[:64] or None
    
    await broadcast_message({"type": "CHAT_USER", "id": msg_id, "source": source, "client_id": client_id, "message": req.message})
    
    context_prompt = await get_combined_context_prompt(req.message)
    client_key = (request.client.host if request.client else "unknown")
    await broadcast_message({"type": "HUD_STATUS", "text": "Núcleo cognitivo (Gemini 3) em processamento..."})
    
    try:
        # Buffer for sentence-by-sentence streaming TTS
        sentence_buffer = ""
        full_reply = ""
        
        async def voice_chunk_callback(token: str):
            nonlocal sentence_buffer, full_reply
            full_reply += token
            sentence_buffer += token
            
            # If we find a sentence terminator, synthesize and send (ONLY if voice is enabled)
            if ENABLE_VOICE and any(punct in token for punct in [".", "!", "?", "\n"]):
                clean_sentence = sentence_buffer.strip()
                if len(clean_sentence) > 5: # Avoid synthesizing tiny fragments
                    audio_b64 = await voice_service.generate_speech_base64(clean_sentence)
                    if audio_b64:
                        await broadcast_message({"type": "AUDIO_RESPONSE", "audio": audio_b64})
                    sentence_buffer = ""
            elif not ENABLE_VOICE:
                sentence_buffer = "" # Clear buffer if voice disabled

        # Run with streaming enabled
        reply = await react_agent.run(context_prompt, client_key=client_key, broadcast=broadcast_message, token_callback=voice_chunk_callback)
        
        # Synthesize any remaining text in buffer (ONLY if voice is enabled)
        if ENABLE_VOICE and sentence_buffer.strip():
            audio_b64 = await voice_service.generate_speech_base64(sentence_buffer.strip())
            if audio_b64:
                await broadcast_message({"type": "AUDIO_RESPONSE", "audio": audio_b64})

        # Final memory update and logs
        asyncio.create_task(update_memory_after_chat(req.message, reply))
        await broadcast_message({"type": "CHAT_AI", "id": msg_id, "source": source, "client_id": client_id, "message": reply})
        await broadcast_message({"type": "HUD_STATUS", "text": "Aguardando atividade neural..."})
        
        return {"reply": reply, "id": msg_id}
    except Exception as e:
        print(f"[ZEUS CHAT ERROR] {e}")
        return {"error": str(e)}

async def update_memory_after_chat(user_msg, ai_reply):
    global long_term_memory
    try:
        if await asyncio.to_thread(should_extract_memory, user_msg, ai_reply):
            await broadcast_message({"type": "TOOL_LOG", "stage": "running", "tool": "long_term_memory"})
            data = await asyncio.to_thread(extract_memory, user_msg, ai_reply)
            if data:
                long_term_memory = await asyncio.to_thread(update_long_memory, data)
                await broadcast_message({"type": "TOOL_LOG", "stage": "done", "tool": "long_term_memory", "result": {"updated_keys": list(data.keys())}})
    except Exception as e:
        await broadcast_message({"type": "TOOL_LOG", "stage": "step_failed", "tool": "long_term_memory", "error": str(e)})


@app.post("/api/vision/analyze")
async def api_vision_analyze(req: VisionAnalyzeReq, request: Request):
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="Only local requests are allowed.")

    data_url = (req.image_data_url or "").strip()
    if not data_url.startswith("data:image/") or "base64," not in data_url:
        raise HTTPException(status_code=400, detail="image_data_url inválido (esperado data:image/...;base64,...)")

    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question é obrigatório.")

    mode = (req.mode or "auto").strip().lower()
    if mode not in {"auto", "llm", "ocr"}:
        mode = "auto"

    ocr_lang = (req.ocr_lang or "por").strip()

    header, b64 = data_url.split("base64,", 1)
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="base64 inválido.")

    out_dir = os.path.join(BASE_DIR, "scratch", "screens")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    img_path = os.path.join(out_dir, f"client-screen-{ts}.png")
    with open(img_path, "wb") as f:
        f.write(raw)

    await broadcast_message({"type": "HUD_STATUS", "text": "Visão ativa: analisando captura..."})
    await broadcast_message({"type": "TOOL_LOG", "stage": "running", "tool": "screen_process", "args": {"source": "client"}})

    analysis = {}
    if mode in {"auto", "llm"}:
        try:
            analysis["llm"] = await asyncio.to_thread(analyze_image_with_llm, img_path, question=question)
            analysis["mode"] = "llm"
        except Exception as e:
            analysis["llm_error"] = str(e)

    if analysis.get("mode") != "llm" and mode in {"auto", "ocr"}:
        try:
            analysis["ocr"] = await asyncio.to_thread(analyze_with_ocr_fallback, img_path, question=question, ocr_lang=ocr_lang)
            analysis["mode"] = analysis.get("mode") or "ocr"
        except Exception as e:
            analysis["ocr_error"] = str(e)

    await broadcast_message({"type": "TOOL_LOG", "stage": "done", "tool": "screen_process", "result": {"analysis": analysis, "path": img_path}})
    await broadcast_message({"type": "HUD_STATUS", "text": "Aguardando atividade neural..."})

    answer = None
    if analysis.get("mode") == "llm":
        answer = (analysis.get("llm") or {}).get("answer")
    elif analysis.get("mode") == "ocr":
        answer = ((analysis.get("ocr") or {}).get("answer")) if isinstance(analysis.get("ocr"), dict) else None

    if not answer:
        raise HTTPException(status_code=500, detail=f"Falha na análise de visão: {analysis}")

    return {"reply": answer, "analysis_mode": analysis.get("mode"), "image_path": img_path}


@app.post("/api/asr")
async def api_asr(req: ASRReq, request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(status_code=403, detail="Only trusted (local/LAN) requests are allowed.")
    _require_lan_token_for_request(request)

    data_url = (req.audio_data_url or "").strip()
    if "base64," not in data_url:
        raise HTTPException(status_code=400, detail="audio_data_url inválido (esperado data:...;base64,...)")

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
    await broadcast_message({"type": "HUD_STATUS", "text": "ASR backend: transcrevendo áudio..."})
    await broadcast_message({"type": "TOOL_LOG", "stage": "running", "tool": "asr"})
    try:
        result = await asyncio.to_thread(transcribe_audio_bytes, raw, mime=mime, language=lang)
    except Exception as e:
        await broadcast_message({"type": "TOOL_LOG", "stage": "step_failed", "tool": "asr", "error": str(e)})
        await broadcast_message({"type": "HUD_STATUS", "text": "ASR backend falhou."})
        raise HTTPException(status_code=500, detail=str(e))

    await broadcast_message({"type": "TOOL_LOG", "stage": "done", "tool": "asr", "result": {"chars": len(result.get("text") or "")}})
    await broadcast_message({"type": "HUD_STATUS", "text": "Aguardando atividade neural..."})
    return {"text": result.get("text") or "", "meta": result}

async def handle_voice_input(text: str):
    if not text:
        return

    await broadcast_message({
        "type": "CHAT_USER",
        "message": text
    })

    current_node = nodes_data[-1]["rel"] if nodes_data else "N/A"
    behavioral_state = pattern_engine.analyze_behavioral_state()

    mem = format_memory_for_prompt(long_term_memory)
    memory_block = f"--- LONG-TERM MEMORY ---\n{mem}\n------------------------\n\n" if mem else ""
    
    context_prompt = (
        f"--- ZEUS SYSTEM CONTEXT ---\n"
        f"Active Node: {current_node}\n"
        f"Behavioral State: {behavioral_state}\n"
        f"System Mood: {system_mood}\n"
        f"----------------------------\n\n"
        f"{memory_block}"
        f"User via Voice: {text}\n\n"
        f"Você é o ZEUS, um sistema operacional cognitivo altamente inteligente e educado. "
        f"Responda em Português (PT-BR) de forma concisa, elegante e natural. "
        f"Mantenha um tom formal, porém prestativo. Sua resposta será falada em voz alta."
    )

    await broadcast_message({"type": "HUD_STATUS", "text": "Processando comando de voz..."})
    reply = await react_agent.run(context_prompt, client_key="voice", broadcast=broadcast_message)
    await broadcast_message({"type": "HUD_STATUS", "text": "Aguardando atividade neural..."})
    
    await voice_module.speak(reply)

@app.get("/api/status")
async def get_mobile_status(request: Request):
    if not _is_trusted_request(request):
        raise HTTPException(status_code=403, detail="Only trusted (local/LAN) requests are allowed.")
    _require_lan_token_for_request(request)
    cpu_per_core = psutil.cpu_percent(percpu=True)
    cpu_avg = sum(cpu_per_core) / len(cpu_per_core) if cpu_per_core else 0
    ram = psutil.virtual_memory().percent
    
    return {
        "cpu": round(cpu_avg, 1),
        "ram": round(ram, 1),
        "mood": system_mood,
        "active_tasks": total_events,
        "objectives": pattern_engine.analyze_behavioral_state() if hasattr(pattern_engine, 'analyze_behavioral_state') else "Evolving"
    }

@app.websocket("/")
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Detect if this is likely a mobile connection trying to reach the root
    token = websocket.query_params.get("token")
    if token:
        payload = auth.verify_token(token)
        if payload and payload.get("sub") == "zeus_mobile_extension":
            return await websocket_mobile(websocket)
    
    # Standard fallback for browser/PWA clients

    # 1. Tenta extrair token da query string
    token = websocket.query_params.get("token")
    
    # 2. Validação de acesso: Aceita se o host for confiável OU se o token for válido
    is_trusted = _is_trusted_host(getattr(websocket.client, "host", None))
    token_valid = False
    if token:
        payload = auth.verify_token(token)
        if payload:
            token_valid = True
    
    if not (is_trusted or token_valid):
        await websocket.close(code=1008)
        return
        
    await websocket.accept()
    connected_clients.add(websocket)
    memory_summary = build_memory_summary()
    vision_caps = {
        "ocr_available": bool(is_tesseract_available()),
        "client_capture_available": True,
    }
    asr_caps = {
        "backend_asr_available": bool(shutil.which("ffmpeg")) and (importlib.util.find_spec("faster_whisper") is not None),
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
    }
    await websocket.send_text(json.dumps({
        "type": "init_nodes",
        "node_count": len(nodes_data),
        "latest_node": nodes_data[-1]["rel"] if nodes_data else None,
        "memory_summary": memory_summary,
        "vision": vision_caps,
        "asr": asr_caps,
        "system_update": {
            "headline": "Warm boot neural",
            "detail": f"{memory_summary['learned_paths']} trilhas recuperadas do disco.",
        }
    }))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)

@app.websocket("/ws/mobile")
async def websocket_mobile(websocket: WebSocket):
    if not _is_trusted_host(getattr(websocket.client, "host", None)):
        await websocket.close(code=1008)
        return
    # Em modo LAN, exige pareamento adicional (token) para hosts não-locais.
    if ALLOW_LAN and LAN_AUTH_ENABLED and not _is_local_host(getattr(websocket.client, "host", None)):
        provided = _extract_bearer_token(websocket.query_params.get("lan")) or _extract_bearer_token(websocket.query_params.get("lan_token"))
        if not LAN_TOKEN or provided != LAN_TOKEN:
            await websocket.close(code=1008)
            return
    token = websocket.query_params.get("token")
    # JWT Authentication
    payload = auth.verify_token(token)
    if not payload:
        await websocket.close(code=1008)
        return
        
    await websocket.accept()
    mobile_clients.add(websocket)
    await websocket.send_json({
        "type": "session_ready",
        "payload": {
            "voice_enabled": bool(ENABLE_VOICE),
            "lan_auth_enabled": bool(ALLOW_LAN and LAN_AUTH_ENABLED),
        },
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})
            
            if msg_type == "command":
                cmd = payload.get("text", "")
                if cmd:
                    await broadcast_message({"type": "CHAT_USER", "message": f"[CMD] {cmd}"})
                    reply = await react_agent.run(f"User Command from Mobile: {cmd}", client_key="mobile", broadcast=broadcast_message)
                    await broadcast_message({"type": "CHAT_AI", "message": reply})
                    await speak(reply)
            
            elif msg_type == "chat":
                msg = payload.get("text", "")
                if msg:
                    silent_mobile_tts = bool(payload.get("silent_mobile_tts", False))
                    await broadcast_message({"type": "CHAT_USER", "message": msg})
                    context_prompt = await get_combined_context_prompt(msg)
                    reply = await react_agent.run(context_prompt, client_key="mobile", broadcast=broadcast_message)
                    await broadcast_message({"type": "CHAT_AI", "message": reply})
                    await speak(reply, target="notebook" if silent_mobile_tts else "all")
                    
            elif msg_type == "voice":
                audio_b64 = payload.get("audio", "")
                if audio_b64:
                    try:
                        raw = base64.b64decode(audio_b64.split(",")[-1] if "," in audio_b64 else audio_b64, validate=False)
                        result = await asyncio.to_thread(transcribe_audio_bytes, raw, mime="audio/webm", language="pt")
                        text = result.get("text") or ""
                        if text:
                            await broadcast_message({"type": "CHAT_USER", "message": f"🎙️ {text}"})
                            context_prompt = await get_combined_context_prompt(text)
                            reply = await react_agent.run(context_prompt, client_key="mobile", broadcast=broadcast_message)
                            await broadcast_message({"type": "CHAT_AI", "message": reply})
                            await speak(reply)
                    except Exception as e:
                        await broadcast_message({"type": "alert", "level": "error", "message": f"Erro ASR Mobile: {str(e)}"})
            
            elif msg_type == "device_register":
                device_id = payload.get("device_id")
                fcm_token = payload.get("fcm_token")
                if device_id and fcm_token:
                    mobile_fcm_tokens[device_id] = fcm_token
                    print(f"📱 Device registered for Push: {device_id}")

            elif msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "payload": {"ts": int(time.time() * 1000)},
                })

            elif msg_type == "system_control":
                action = payload.get("action")
                if action == "execute_command":
                    command = payload.get("command")
                    # Pass through React Agent for Guardian validation
                    await broadcast_message({"type": "HUD_STATUS", "text": f"Validando comando remoto: {command}"})
                    reply = await react_agent.run(f"Remote System Control: Execute {command}", client_key="mobile", broadcast=broadcast_message)
                    await websocket.send_json({"type": "control_result", "payload": {"result": reply}})

            elif msg_type == "goal":
                # Handle cognitive goals
                goal_data = payload.get("goal")
                if goal_data:
                    await broadcast_message({"type": "HUD_STATUS", "text": "Novo objetivo recebido via Mobile"})
                    await react_agent.run(f"User sets a new GOAL: {goal_data}", client_key="mobile", broadcast=broadcast_message)

    except WebSocketDisconnect:
        mobile_clients.discard(websocket)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro no WebSocket Mobile: {e}")
        mobile_clients.discard(websocket)

@sio.on("arm_voice")
async def handle_arm_voice(sid, data):
    duration = data.get("duration", 10)
    if voice_module:
        voice_module.arm(seconds=duration)
        await broadcast_message({"type": "HUD_STATUS", "text": f"Escuta manual ativada ({duration}s)"})

app.mount("/socket.io", socketio.ASGIApp(sio))
# asgi_app = app # No longer need a wrapper if we use mount


if __name__ == "__main__":
    import uvicorn
    import sys

    if "--desktop" in sys.argv:
        # Modo Desktop com GUI
        from PyQt6.QtWidgets import QApplication, QMainWindow
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtCore import QUrl
        import threading

        def run_uvicorn():
            try:
                ssl_opts = {}
                if (not DISABLE_SSL) and os.path.exists("configs/key.pem") and os.path.exists("configs/cert.pem"):
                    ssl_opts = {"ssl_keyfile": "configs/key.pem", "ssl_certfile": "configs/cert.pem"}
                uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="error", **ssl_opts)
            except Exception as e:
                print(f"Server Error: {e}")

        t = threading.Thread(target=run_uvicorn, daemon=True)
        t.start()
        time.sleep(2)

        qt_app = QApplication(sys.argv)
        window = QMainWindow()
        window.setWindowTitle("ZEUS Command Center")
        window.resize(1440, 810)
        
        # QWebEngineView Configs
        browser = QWebEngineView()
        settings = browser.settings()
        settings.setAttribute(settings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(settings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(settings.WebAttribute.JavascriptCanAccessClipboard, True)
        
        use_https = (not DISABLE_SSL) and os.path.exists("configs/key.pem")
        browser.setUrl(QUrl(f"https://127.0.0.1:{SERVER_PORT}" if use_https else f"http://127.0.0.1:{SERVER_PORT}"))
        
        # Permissões automáticas (Microfone, etc)
        def handle_feature_permission(url, feature):
            browser.page().setFeaturePermission(url, feature, browser.page().FeaturePermission.PermissionGrantedByUser)
        
        browser.page().featurePermissionRequested.connect(handle_feature_permission)
        
        def handle_cert_error(error):
            error.acceptCertificate()
            return True
        browser.page().certificateError.connect(handle_cert_error)
        
        window.setCentralWidget(browser)
        window.show()
        sys.exit(qt_app.exec())
    elif "--headless" in sys.argv or "--server" in sys.argv:
        # Modo Servidor Puro (Headless)
        print(f"🌑 ZEUS em modo HEADLESS operacional em {SERVER_HOST}:{SERVER_PORT}")
        ssl_opts = {}
        if not DISABLE_SSL:
            if os.path.exists("configs/key.pem") and os.path.exists("configs/cert.pem"):
                ssl_opts = {"ssl_keyfile": "configs/key.pem", "ssl_certfile": "configs/cert.pem"}
            elif os.path.exists("key.pem") and os.path.exists("cert.pem"):
                ssl_opts = {"ssl_keyfile": "key.pem", "ssl_certfile": "cert.pem"}
        
        # Log level reduzido para não poluir o terminal headless
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning", **ssl_opts)
    else:
        # Modo Web padrão
        ssl_opts = {}
        if not DISABLE_SSL:
            if os.path.exists("configs/key.pem") and os.path.exists("configs/cert.pem"):
                ssl_opts = {"ssl_keyfile": "configs/key.pem", "ssl_certfile": "configs/cert.pem"}
            elif os.path.exists("key.pem") and os.path.exists("cert.pem"):
                ssl_opts = {"ssl_keyfile": "key.pem", "ssl_certfile": "cert.pem"}
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, **ssl_opts)
