import sqlite3
import os
import json

from zeus_core.env import load_project_env

load_project_env()

DB_PATH = os.getenv("ZEUS_DB_PATH", "./zeus_events.db")


def get_connection(db_path: str | None = None):
    return sqlite3.connect(db_path or os.getenv("ZEUS_DB_PATH", DB_PATH))


def init_db(db_path: str | None = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Events Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            source_path TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            error_message TEXT
        )
    """)

    # Processed Files (Cache by Hash)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            content_hash TEXT NOT NULL,
            last_modified TIMESTAMP,
            last_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            detected_tags TEXT,
            status TEXT DEFAULT 'ok'
        )
    """)

    # Sync Logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            source_path TEXT NOT NULL,
            target_id TEXT,
            status TEXT DEFAULT 'success',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error_message TEXT
        )
    """)

    # External Links Mapping
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS external_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obsidian_path TEXT UNIQUE NOT NULL,
            notion_page_id TEXT,
            linear_issue_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# DAO Functions
def insert_event(event_type: str, source: str, source_path: str, payload: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO events (event_type, source, source_path, payload_json)
        VALUES (?, ?, ?, ?)
    """,
        (event_type, source, source_path, json.dumps(payload)),
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_file_hash(file_path: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content_hash FROM processed_files WHERE file_path = ?", (file_path,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def update_file_hash(file_path: str, content_hash: str, tags: list):
    conn = get_connection()
    cursor = conn.cursor()
    tags_str = json.dumps(tags)

    cursor.execute("SELECT id FROM processed_files WHERE file_path = ?", (file_path,))
    if cursor.fetchone():
        cursor.execute(
            """
            UPDATE processed_files 
            SET content_hash = ?, last_processed_at = CURRENT_TIMESTAMP, detected_tags = ?
            WHERE file_path = ?
        """,
            (content_hash, tags_str, file_path),
        )
    else:
        cursor.execute(
            """
            INSERT INTO processed_files (file_path, content_hash, detected_tags)
            VALUES (?, ?, ?)
        """,
            (file_path, content_hash, tags_str),
        )

    conn.commit()
    conn.close()


def link_external_resource(
    obsidian_path: str, notion_id: str = None, linear_id: str = None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, notion_page_id, linear_issue_id FROM external_links WHERE obsidian_path = ?",
        (obsidian_path,),
    )
    row = cursor.fetchone()

    if row:
        n_id = notion_id if notion_id else row[1]
        l_id = linear_id if linear_id else row[2]
        cursor.execute(
            """
            UPDATE external_links 
            SET notion_page_id = ?, linear_issue_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE obsidian_path = ?
        """,
            (n_id, l_id, obsidian_path),
        )
    else:
        cursor.execute(
            """
            INSERT INTO external_links (obsidian_path, notion_page_id, linear_issue_id)
            VALUES (?, ?, ?)
        """,
            (obsidian_path, notion_id, linear_id),
        )

    conn.commit()
    conn.close()


def get_sync_status() -> dict:
    """Returns sync event counters and last sync timestamps."""
    conn = get_connection()
    cursor = conn.cursor()

    status = {
        "total_events": 0,
        "pending": 0,
        "processed": 0,
        "error": 0,
        "last_sync": None,
    }

    try:
        cursor.execute("SELECT status, COUNT(*) FROM events GROUP BY status")
        for event_status, count in cursor.fetchall():
            status[event_status or "unknown"] = count
            status["total_events"] += count

        cursor.execute(
            "SELECT MAX(processed_at) FROM events WHERE status = 'processed'"
        )
        row = cursor.fetchone()
        if row and row[0]:
            status["last_sync"] = row[0]

        cursor.execute("SELECT COUNT(*) FROM sync_logs")
        status["total_sync_ops"] = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(created_at) FROM sync_logs")
        row = cursor.fetchone()
        if row and row[0]:
            status["last_sync_op"] = row[0]
    except Exception as e:
        status["error_detail"] = str(e)

    conn.close()
    return status


def log_sync_event(
    source: str,
    target: str,
    source_path: str,
    target_id: str = None,
    status: str = "success",
    error_message: str = None,
):
    """Registra uma operação de sincronização no banco."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO sync_logs (source, target, source_path, target_id, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (source, target, source_path, target_id, status, error_message),
    )
    conn.commit()
    conn.close()


def was_already_synced(source: str, target: str, source_path: str) -> bool:
    """Verifica se um item já foi sincronizado com sucesso para evitar duplicatas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM sync_logs 
        WHERE source = ? AND target = ? AND source_path = ? AND status = 'success'
    """,
        (source, target, source_path),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0
