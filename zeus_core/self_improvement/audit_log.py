import os
import json
import sqlite3
import datetime
from zeus_core.observability import get_logger

logger = get_logger("zeus.self_improvement.audit")


class AuditLog:
    def __init__(self):
        self.db_path = os.path.join(
            os.getenv("ZEUS_VAULT_PATH", "/home/zeus/Documentos/Brain"),
            "logs",
            "self_improvement_audit.db",
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patches (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                files_changed TEXT,
                diff TEXT,
                status TEXT,
                reason TEXT
            )
        """)
        conn.close()

    def record_patch(
        self, patch_id: str, files_changed: list, diff: str, status: str, reason: str
    ):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO patches (id, timestamp, files_changed, diff, status, reason) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    patch_id,
                    datetime.datetime.now().isoformat(),
                    json.dumps(files_changed),
                    diff,
                    status,
                    reason,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_history(self, limit: int = 50):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM patches ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows


audit_log = AuditLog()
