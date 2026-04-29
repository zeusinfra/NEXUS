import os
import sqlite3
import json
import time
from collections import deque
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

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
        self.logger = logging.getLogger("ZEUS_MEMORY")
        
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                path TEXT PRIMARY KEY,
                weight INTEGER DEFAULT 1,
                last_accessed TIMESTAMP,
                metadata JSON
            )
        ''')
        
        # Table for Synaptic Connections (Edges)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS synapses (
                source TEXT,
                target TEXT,
                weight INTEGER DEFAULT 1,
                last_interaction TIMESTAMP,
                PRIMARY KEY (source, target),
                FOREIGN KEY (source) REFERENCES nodes(path),
                FOREIGN KEY (target) REFERENCES nodes(path)
            )
        ''')
        
        # Table for Behavioral Patterns
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                context TEXT,
                timestamp TIMESTAMP,
                importance REAL
            )
        ''')
        
        conn.commit()
        conn.close()

    # --- L1: Sensory Memory Methods ---
    def record_sensation(self, event: dict):
        """Records an immediate event in the volatile sensory buffer."""
        event['processed_at'] = time.time()
        self.sensory_history.append(event)
        
    def get_recent_context(self, limit=10) -> List[dict]:
        return list(self.sensory_history)[-limit:]

    # --- L2: Working Memory Methods (SQLite) ---
    def update_synapse(self, source: str, target: str, weight_inc: int = 1):
        """Updates or creates a connection between two nodes in L2."""
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
            cursor.execute('''
                INSERT INTO nodes (path, weight, last_accessed)
                VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    weight = weight + 1,
                    last_accessed = excluded.last_accessed
            ''', (path, 1, now))
            
        # Update/Insert Synapse
        cursor.execute('''
            INSERT INTO synapses (source, target, weight, last_interaction)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source, target) DO UPDATE SET
                weight = weight + ?,
                last_interaction = excluded.last_interaction
        ''', (source, target, weight_inc, now, weight_inc))
        
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
        cursor.execute('''
            SELECT target FROM synapses 
            WHERE source = ? 
            ORDER BY weight DESC, last_interaction DESC 
            LIMIT ?
        ''', (path, limit))
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
        cursor.execute('UPDATE synapses SET weight = MAX(1, CAST(weight * ? AS INTEGER))', (factor,))
        cursor.execute('UPDATE nodes SET weight = MAX(1, CAST(weight * ? AS INTEGER))', (factor,))
        conn.commit()
        conn.close()
        self.logger.info("Memory decay applied to L2.")

    def export_legacy_json(self) -> dict:
        """Converts SQLite state back to the legacy JSON format for backward compatibility."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT path, weight FROM nodes')
        nodes = cursor.fetchall()
        
        memory = {}
        for path, weight in nodes:
            cursor.execute('SELECT target FROM synapses WHERE source = ?', (path,))
            conns = [r[0] for r in cursor.fetchall()]
            memory[path] = {
                "weight": weight,
                "connections": conns
            }
        
        conn.close()
        return memory
