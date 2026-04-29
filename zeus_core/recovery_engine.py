
import json
import os
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

class RecoveryEngine:
    """
    PHASE 11: Self-Recovery.
    Ensures system survival by detecting crashes and restoring state from snapshots.
    """
    def __init__(self, blackboard, storage_path: str = "recovery_snapshots/"):
        self.blackboard = blackboard
        self.storage_path = storage_path
        self.logger = logging.getLogger("ZEUS_RECOVERY")
        self._setup_snapshot_dir()

    def _setup_snapshot_dir(self):
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    def create_snapshot(self, label: str = "auto"):
        """Saves a full state snapshot of the Blackboard to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{label}_{timestamp}.json"
        path = os.path.join(self.storage_path, filename)
        
        try:
            state = self.blackboard.get_all() # Assumes Blackboard has a get_all() method
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            
            self.logger.info(f"Snapshot created: {filename}")
            return path
        except Exception as e:
            self.logger.error(f"Snapshot failed: {e}")
            return None

    def detect_crash(self) -> bool:
        """
        Analyzes boot logs or blackboard flags to detect if the previous 
        shutdown was abnormal (crash).
        """
        # Simple heuristic: check for an 'active' flag left over from a previous session
        flag_file = os.path.join(self.storage_path, ".system_active")
        if os.path.exists(flag_file):
            self.logger.warning("System crash detected: Active flag was found from previous session.")
            return True
        return False

    def restore_last_snapshot(self) -> bool:
        """Restores the system state from the most recent successful snapshot."""
        snapshots = sorted(
            [f for f in os.listdir(self.storage_path) if f.startswith("snapshot_")],
            reverse=True
        )
        
        if not snapshots:
            self.logger.info("No snapshots available for recovery.")
            return False
            
        try:
            last_snapshot = os.path.join(self.storage_path, snapshots[0])
            with open(last_snapshot, "r", encoding="utf-8") as f:
                state = json.load(f)
                
            # Re-inject state into Blackboard
            for key, value in state.items():
                self.blackboard.update(key, value)
                
            self.logger.info(f"Recovery successful. Restored state from {snapshots[0]}")
            return True
        except Exception as e:
            self.logger.critical(f"Recovery FAILED: {e}")
            return False

    def perform_emergency_rollback(self, execution_engine):
        """Triggers the execution engine's rollback if a critical failure is detected."""
        if execution_engine:
            self.logger.info("Triggering emergency rollback of last action...")
            return execution_engine.rollback()
        return False
