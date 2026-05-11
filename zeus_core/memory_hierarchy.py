import json
import os
import logging
from typing import Dict, Any
from datetime import datetime


class MemoryHierarchy:
    """
    PHASE 8: Memory Hierarchy.
    Manages cognitive load by splitting memory into three layers:
    - Short-Term: Volatile, high-speed context.
    - Mid-Term: Pattern-based, persistent across cycles.
    - Long-Term: Vector-based, scalable knowledge store.
    """

    def __init__(self, blackboard, storage_path: str = "memory_hierarchy.json"):
        self.blackboard = blackboard
        self.storage_path = storage_path
        self.logger = logging.getLogger("NEXUS_MEMORY")

        # Layers
        self.short_term: Dict[str, Any] = {}  # Contextual window
        self.mid_term: Dict[str, Any] = {}  # Pattern/Strategy history
        self.long_term_path = os.path.join(
            os.path.dirname(__file__), "../vector_memory.json"
        )

        self.load_persistent_memory()

    def update_short_term(self, key: str, value: Any):
        """Updates the immediate volatile context."""
        self.short_term[key] = {"value": value, "timestamp": datetime.now().isoformat()}
        # Prevent overflow: Keep only the last 50 items
        if len(self.short_term) > 50:
            oldest_key = next(iter(self.short_term))
            del self.short_term[oldest_key]

    def commit_to_mid_term(self, key: str, value: Any, importance: float = 1.0):
        """Promotes Short-Term knowledge to Mid-Term if it shows a pattern."""
        if importance > 0.7:
            self.mid_term[key] = {
                "value": value,
                "weight": importance,
                "last_accessed": datetime.now().isoformat(),
            }
            self.save_persistent_memory()

    def query_memory(self, query: str) -> Dict[str, Any]:
        """Hierarchical search: Short-term -> Mid-term -> Long-term."""
        # 1. Check Short-Term (Immediate match)
        if query in self.short_term:
            return {"layer": "short_term", "data": self.short_term[query]["value"]}

        # 2. Check Mid-Term (Pattern match)
        if query in self.mid_term:
            return {"layer": "mid_term", "data": self.mid_term[query]["value"]}

        # 3. Long-Term (Vector DB search handled by VectorMemory module)
        return {
            "layer": "long_term",
            "data": None,
            "hint": "Consult VectorMemory for semantic match",
        }

    def compress_memory(self):
        """Automatic compression: Reduces Mid-Term noise."""
        # Prune Mid-Term items with weight <<  0.3
        keys_to_prune = [
            k for k, v in self.mid_term.items() if v.get("weight", 1.0) << 0.3
        ]
        for k in keys_to_prune:
            del self.mid_term[k]
        self.save_persistent_memory()
        self.logger.info(
            f"Memory compression completed. Pruned {len(keys_to_prune)} items."
        )

    def save_persistent_memory(self):
        """Saves Mid-Term layer to disk using atomic write."""
        try:
            temp_file = self.storage_path + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.mid_term, f, indent=2)
            os.replace(temp_file, self.storage_path)
        except Exception as e:
            self.logger.error(f"Failed to save memory hierarchy: {e}")

    def load_persistent_memory(self):
        """Loads Mid-Term layer from disk."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self.mid_term = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load memory hierarchy: {e}")
