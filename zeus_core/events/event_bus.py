import time
import json
import os
from zeus_core.memory.sqlite_memory import get_connection, insert_event, get_file_hash, update_file_hash
from zeus_core.integrations.obsidian import read_note

# Simple in-memory debounce cache: {file_path: last_trigger_timestamp}
_debounce_cache = {}
DEBOUNCE_MS = int(os.getenv("ZEUS_WATCHER_DEBOUNCE_MS", "1200") or "1200")

def publish_file_event(file_path: str, source: str = "obsidian"):
    """
    Publica um evento se o arquivo realmente mudou (hash diferente)
    e passou pelo período de debounce.
    """
    current_time = time.time() * 1000
    last_trigger = _debounce_cache.get(file_path, 0)
    
    if current_time - last_trigger < DEBOUNCE_MS:
        # Ignora evento muito próximo (debounce)
        return False
        
    _debounce_cache[file_path] = current_time
    
    try:
        note_data = read_note(file_path)
    except Exception as e:
        print(f"[EventBus] Erro ao ler nota {file_path}: {e}")
        return False

    current_hash = note_data['hash']
    stored_hash = get_file_hash(file_path)
    
    if current_hash != stored_hash:
        # Arquivo realmente mudou
        update_file_hash(file_path, current_hash, note_data['tags'])
        
        # Insere evento para processamento assíncrono
        event_id = insert_event(
            event_type="FILE_MODIFIED",
            source=source,
            source_path=file_path,
            payload=note_data
        )
        print(f"[EventBus] Novo evento registrado (ID: {event_id}) para {file_path}")
        return True
        
    return False

def get_pending_events(limit: int = 10):
    """Retorna os próximos eventos pendentes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, event_type, source, source_path, payload_json 
        FROM events 
        WHERE status = 'pending' 
        ORDER BY created_at ASC 
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    events = []
    for row in rows:
        events.append({
            "id": row[0],
            "event_type": row[1],
            "source": row[2],
            "source_path": row[3],
            "payload": json.loads(row[4])
        })
    return events

def mark_event_processed(event_id: int, status: str = 'processed', error_message: str = None):
    """Atualiza o status de um evento após processamento."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE events 
        SET status = ?, processed_at = CURRENT_TIMESTAMP, error_message = ?
        WHERE id = ?
    ''', (status, error_message, event_id))
    conn.commit()
    conn.close()

# --- NOVO SISTEMA DE EVENTOS ASYNC (PUB/SUB) ---
import asyncio
from typing import Callable, Dict, List, Any, Awaitable
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    FILE_CHANGED = "FILE_CHANGED"
    COMMAND_FAILED = "COMMAND_FAILED"
    BUILD_FAILED = "BUILD_FAILED"
    HIGH_RAM_USAGE = "HIGH_RAM_USAGE"
    HIGH_CPU_USAGE = "HIGH_CPU_USAGE"
    HIGH_SWAP_USAGE = "HIGH_SWAP_USAGE"
    DISK_PRESSURE = "DISK_PRESSURE"
    USER_IDLE = "USER_IDLE"
    USER_ACTIVE = "USER_ACTIVE"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    TOOL_FAILED = "TOOL_FAILED"
    AGENT_LOOP_DETECTED = "AGENT_LOOP_DETECTED"
    DAEMON_EXECUTE = "DAEMON_EXECUTE"
    DAEMON_BLOCKED = "DAEMON_BLOCKED"
    DAEMON_APPROVAL_REQUIRED = "DAEMON_APPROVAL_REQUIRED"
    DAEMON_APPROVED = "DAEMON_APPROVED"
    DAEMON_DENIED = "DAEMON_DENIED"
    PERIPHERAL_CONNECTED = "PERIPHERAL_CONNECTED"
    PERIPHERAL_DISCONNECTED = "PERIPHERAL_DISCONNECTED"
    SELF_IMPROVEMENT_STARTED = "SELF_IMPROVEMENT_STARTED"
    SELF_IMPROVEMENT_FAILED = "SELF_IMPROVEMENT_FAILED"
    SELF_IMPROVEMENT_APPLIED = "SELF_IMPROVEMENT_APPLIED"
    CONVERSATION_TOPIC_SHIFT = "CONVERSATION_TOPIC_SHIFT"
    CONVERSATION_CONCAT_DETECTED = "CONVERSATION_CONCAT_DETECTED"
    CONTEXT_TOO_LARGE = "CONTEXT_TOO_LARGE"
    RESPONSE_DUPLICATED = "RESPONSE_DUPLICATED"

class Event:
    def __init__(self, event_type: EventType | str, payload: dict | None = None):
        self.type = event_type if isinstance(event_type, str) else event_type.value
        self.payload = payload or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp
        }

    def __str__(self):
        return json.dumps(self.to_dict())


class EventBus:
    """Pub/Sub mechanism for ZEUS components."""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._subscribers: Dict[str, List[Callable[[Event], Awaitable[None]]]] = {}
        self._global_subscribers: List[Callable[[Event], Awaitable[None]]] = []
        self._queue = asyncio.Queue()
        self._task = None
        self._initialized = True

    def subscribe(self, event_type: str | EventType, callback: Callable[[Event], Awaitable[None]]):
        event_str = event_type if isinstance(event_type, str) else event_type.value
        if event_str not in self._subscribers:
            self._subscribers[event_str] = []
        self._subscribers[event_str].append(callback)

    def subscribe_all(self, callback: Callable[[Event], Awaitable[None]]):
        self._global_subscribers.append(callback)

    def publish(self, event_type: str | EventType, payload: dict | None = None):
        """Async safe publishing using the event loop's task or queue"""
        event = Event(event_type, payload)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self._queue.put(event))
        except RuntimeError:
            pass # Sem loop

    async def publish_async(self, event_type: str | EventType, payload: dict | None = None):
        event = Event(event_type, payload)
        await self._queue.put(event)

    async def _dispatch_loop(self):
        while True:
            event = await self._queue.get()
            
            for callback in self._global_subscribers:
                try:
                    await callback(event)
                except Exception as e:
                    print(f"Erro no subscriber global ao processar {event.type}: {e}")

            if event.type in self._subscribers:
                for callback in self._subscribers[event.type]:
                    try:
                        await callback(event)
                    except Exception as e:
                        print(f"Erro no subscriber de {event.type}: {e}")
            
            self._queue.task_done()

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._dispatch_loop())

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

# Singleton instance exportada
event_bus = EventBus()
