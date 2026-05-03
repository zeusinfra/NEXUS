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
