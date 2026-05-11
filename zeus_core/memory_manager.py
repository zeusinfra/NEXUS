import os
import sqlite3
import time
from collections import deque
from datetime import datetime
from typing import List
import logging

from zeus_core.path_filters import is_runtime_noise_path

try:
    from zeus_synapse import SynapseManagerRust

    SYNAPSE_RUST_AVAILABLE = True
except ImportError:
    SYNAPSE_RUST_AVAILABLE = False


class MemoryManager:
    """
    ZEUS Memory Manager (PHASE 4 - Tiered Architecture)
    Orchestrates Sensory (L1), Working (L2), and Long-Term (L3) memory layers.
    """

    def __init__(self, db_path="data/zeus_memory.db", vector_memory=None):
        self.db_path = db_path
        self.vector_memory = vector_memory
        self.logger = logging.getLogger("NEXUS_MEMORY")

        # L1: Sensory Memory (Volatile RAM)
        self.sensory_history = deque(maxlen=200)

        # Initialize L2: Working Memory (SQLite)
        self._init_db()

        if SYNAPSE_RUST_AVAILABLE:
            print("🦀 ZEUS: Usando Backend Rust para Sinapses (L2).")
            self.rust_synapse = SynapseManagerRust(db_path)
        else:
            print("🐍 ZEUS: Usando Backend Python para Sinapses (L2).")
            self.rust_synapse = None

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table for Synaptic Nodes (Paths/Files)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                path TEXT PRIMARY KEY,
                weight INTEGER DEFAULT 1,
                last_accessed TIMESTAMP,
                metadata JSON
            )
        """)

        # Table for Synaptic Connections (Edges)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synapses (
                source TEXT,
                target TEXT,
                weight INTEGER DEFAULT 1,
                last_interaction TIMESTAMP,
                PRIMARY KEY (source, target),
                FOREIGN KEY (source) REFERENCES nodes(path),
                FOREIGN KEY (target) REFERENCES nodes(path)
            )
        """)

        # Table for Behavioral Patterns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                context TEXT,
                timestamp TIMESTAMP,
                importance REAL
            )
        """)

        conn.commit()
        conn.close()

    # --- L1: Sensory Memory Methods ---
    def record_sensation(self, event: dict):
        """Records an immediate event in the volatile sensory buffer."""
        event["processed_at"] = time.time()
        self.sensory_history.append(event)

    def get_recent_context(self, limit=10) -> List[dict]:
        return list(self.sensory_history)[-limit:]

    # --- L2: Working Memory Methods (SQLite) ---
    def update_synapse(self, source: str, target: str, weight_inc: int = 1):
        """Updates or creates a connection between two nodes in L2."""
        if is_runtime_noise_path(source) or is_runtime_noise_path(target):
            return

        if self.rust_synapse:
            try:
                self.rust_synapse.update_synapse(source, target, weight_inc)
                return
            except Exception as e:
                self.logger.error(f"Rust Synapse Error: {e}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        # Update/Insert Nodes
        for path in [source, target]:
            cursor.execute(
                """
                INSERT INTO nodes (path, weight, last_accessed)
                VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    weight = weight + 1,
                    last_accessed = excluded.last_accessed
            """,
                (path, 1, now),
            )

        # Update/Insert Synapse
        cursor.execute(
            """
            INSERT INTO synapses (source, target, weight, last_interaction)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source, target) DO UPDATE SET
                weight = weight + ?,
                last_interaction = excluded.last_interaction
        """,
            (source, target, weight_inc, now, weight_inc),
        )

        conn.commit()
        conn.close()

    def get_working_context(self, path: str, limit=5) -> List[str]:
        """Retrieves related paths (synapses) from L2."""
        if self.rust_synapse:
            try:
                return self.rust_synapse.get_working_context(path, limit)
            except Exception as e:
                self.logger.error(f"Rust Synapse Recall Error: {e}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT target FROM synapses 
            WHERE source = ? 
            ORDER BY weight DESC, last_interaction DESC 
            LIMIT ?
        """,
            (path, limit),
        )
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results

    # --- L3: Long-Term Memory (Vector Integration) ---
    def promote_to_long_term(self, path: str, content: str = None):
        """Indexes a node semantically in L3."""
        if self.vector_memory:
            if content:
                self.vector_memory.index_text(path, content)
            else:
                self.vector_memory.index_file(path)

    def deep_recall(self, query: str, top_k=3):
        """Semantic search in L3."""
        if self.vector_memory:
            return self.vector_memory.find_similar(query, top_k=top_k)
        return []

    # --- Maintenance ---
    def decay_memory(self, factor=0.95):
        """Applies aging to synapses in L2 to simulate forgetting unimportant data."""
        if self.rust_synapse:
            try:
                self.rust_synapse.decay_memory(factor)
                self.logger.info("Memory decay applied to L2 (Rust).")
                return
            except Exception as e:
                self.logger.error(f"Rust Decay Error: {e}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE synapses SET weight = MAX(1, CAST(weight * ? AS INTEGER))",
            (factor,),
        )
        cursor.execute(
            "UPDATE nodes SET weight = MAX(1, CAST(weight * ? AS INTEGER))", (factor,)
        )
        conn.commit()
        conn.close()
        self.logger.info("Memory decay applied to L2.")

    def export_legacy_json(self) -> dict:
        """Converts SQLite state back to the legacy JSON format for backward compatibility."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT path, weight FROM nodes")
        nodes = cursor.fetchall()

        memory = {}
        for path, weight in nodes:
            cursor.execute("SELECT target FROM synapses WHERE source = ?", (path,))
            conns = [r[0] for r in cursor.fetchall()]
            memory[path] = {"weight": weight, "connections": conns}

        conn.close()
        return memory

    def export_sync_snapshot(
        self, top_nodes: int = 20, top_synapses: int = 15, top_patterns: int = 10
    ) -> dict:
        """
        Exports a clean snapshot of the synaptic memory state for synchronization.
        Returns top nodes by weight, strongest synapses, and recent patterns.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Top nodes by weight
        cursor.execute(
            "SELECT path, weight, last_accessed FROM nodes ORDER BY weight DESC LIMIT ?",
            (top_nodes,),
        )
        nodes = [
            {"path": r[0], "weight": r[1], "last_accessed": r[2]}
            for r in cursor.fetchall()
        ]

        # Strongest synapses
        cursor.execute(
            """
            SELECT source, target, weight, last_interaction 
            FROM synapses ORDER BY weight DESC LIMIT ?
        """,
            (top_synapses,),
        )
        synapses = [
            {"source": r[0], "target": r[1], "weight": r[2], "last_interaction": r[3]}
            for r in cursor.fetchall()
        ]

        # Recent patterns
        cursor.execute(
            """
            SELECT type, context, timestamp, importance 
            FROM patterns ORDER BY timestamp DESC LIMIT ?
        """,
            (top_patterns,),
        )
        patterns = [
            {"type": r[0], "context": r[1], "timestamp": r[2], "importance": r[3]}
            for r in cursor.fetchall()
        ]

        # Summary stats
        cursor.execute("SELECT COUNT(*) FROM nodes")
        total_nodes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM synapses")
        total_synapses = cursor.fetchone()[0]

        conn.close()

        return {
            "timestamp": datetime.now().isoformat(),
            "total_nodes": total_nodes,
            "total_synapses": total_synapses,
            "top_nodes": nodes,
            "top_synapses": synapses,
            "recent_patterns": patterns,
            "sensory_buffer_size": len(self.sensory_history),
        }

    # Extensions that are internal runtime artifacts, not meaningful code activity
    _NOISE_EXTENSIONS = {
        ".db",
        ".db-journal",
        ".db-wal",
        ".db-shm",
        ".log",
        ".tmp",
        ".apk",
        ".so",
        ".bin",
        ".json",
        ".pyc",
        ".lock",
        ".pid",
        ".jar",
        ".ap_",
        ".txt",
        ".dex",
        ".class",
        ".idx",
        ".pack",
    }

    def _is_noise_path(self, path: str) -> bool:
        """Filters out internal system/runtime files from anomaly detection."""
        if is_runtime_noise_path(path):
            return True
        basename = os.path.basename(path)
        _, ext = os.path.splitext(basename)
        return ext.lower() in self._NOISE_EXTENSIONS

    def get_anomalies(self, weight_threshold: int = 200) -> list:
        """
        Detects anomalous activity spikes — nodes or synapses with unusually high weight.
        Filters out internal runtime artifacts (db, log, tmp, apk, so).
        Returns a list of anomaly dicts suitable for creating Linear issues.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        anomalies = []

        # Nodes with weight above threshold (fetch extra to compensate for filtering)
        cursor.execute(
            "SELECT path, weight, last_accessed FROM nodes WHERE weight > ? ORDER BY weight DESC LIMIT 30",
            (weight_threshold,),
        )
        for r in cursor.fetchall():
            if self._is_noise_path(r[0]):
                continue
            anomalies.append(
                {
                    "type": "high_activity_node",
                    "path": r[0],
                    "weight": r[1],
                    "last_accessed": r[2],
                    "title": f"Atividade anômala: {os.path.basename(r[0])}",
                    "description": f"Nó sináptico '{r[0]}' atingiu peso {r[1]}, indicando foco intenso ou loop de processamento.",
                    "priority": "high" if r[1] > weight_threshold * 2 else "medium",
                }
            )
            if len(anomalies) >= 5:
                break

        # Synapses with extreme weight
        synapse_count = 0
        cursor.execute(
            "SELECT source, target, weight FROM synapses WHERE weight > ? ORDER BY weight DESC LIMIT 20",
            (weight_threshold,),
        )
        for r in cursor.fetchall():
            if self._is_noise_path(r[0]) or self._is_noise_path(r[1]):
                continue
            anomalies.append(
                {
                    "type": "strong_synapse",
                    "source": r[0],
                    "target": r[1],
                    "weight": r[2],
                    "title": f"Sinapse forte: {os.path.basename(r[0])} ↔ {os.path.basename(r[1])}",
                    "description": f"Conexão entre '{r[0]}' e '{r[1]}' com peso {r[2]}. Pode indicar dependência crítica.",
                    "priority": "medium",
                }
            )
            synapse_count += 1
            if synapse_count >= 3:
                break

        conn.close()
        return anomalies
