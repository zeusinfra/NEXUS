
import os
import subprocess
import shutil
import logging
import datetime
import shlex
from pathlib import Path
from typing import Dict, Any, Optional

from zeus_core.command_policy import validate_command
from zeus_core.tools import ToolError

class ExecutionEngine:
    """
    PHASE 6: Execution Engine.
    Safe and reversible actions.
    """
    def __init__(self, blackboard, bootstrap_config):
        self.blackboard = blackboard
        self.config = bootstrap_config
        self.logger = logging.getLogger("ZEUS_EXECUTION")
        self.backup_root = Path("/tmp/zeus_backups")
        self.action_history = []
        self._setup_backup_dir()

    def _setup_backup_dir(self):
        try:
            if not self.backup_root.exists():
                self.backup_root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Backup dir creation failed: {e}")

    def _create_backup(self, target_paths: list):
        """Creates a timestamped backup of files before modification."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_backup_dir = self.backup_root / timestamp
        session_backup_dir.mkdir(parents=True, exist_ok=True)
        
        backups_created = []
        for path in target_paths:
            try:
                src = Path(path)
                if src.exists() and src.is_file():
                    dest = session_backup_dir / src.name
                    shutil.copy2(src, dest)
                    backups_created.append((src, dest))
            except Exception as e:
                self.logger.warning(f"Backup failed for {path}: {e}")
        
        return backups_created

    async def execute_action(self, command: str, target_files: list = None, confirmed: bool = False) -> Dict[str, Any]:
        """
        Executes a validated and simulated command.
        Provides automatic backup and rollback capabilities.
        """
        # 1. Create Backups
        backups = []
        if target_files:
            backups = self._create_backup(target_files)
        
        self.logger.info(f"Executing Action: {command}")
        
        try:
            tokens = shlex.split(command)
            decision = validate_command(command, tokens, confirmed=confirmed)
            result = subprocess.run(
                tokens,
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            success = result.returncode == 0
            
            action_record = {
                "timestamp": datetime.datetime.now().isoformat(),
                "command": command,
                "category": decision.category,
                "requires_confirmation": decision.requires_confirmation,
                "success": success,
                "output": result.stdout,
                "error": result.stderr,
                "backups": backups,
                "target_files": target_files
            }
            
            self.action_history.append(action_record)
            
            # Update Blackboard
            self.blackboard.update("last_execution", action_record)
            
            return action_record
            
        except ToolError as e:
            self.logger.warning(f"Execution blocked by policy: {e}")
            return {"success": False, "error": str(e), "output": "", "blocked": True}
        except Exception as e:
            self.logger.error(f"Execution Critical Error: {e}")
            return {"success": False, "error": str(e), "output": ""}

    def rollback(self):
        """Reverts the last successful action using the created backups."""
        if not self.action_history:
            self.logger.info("No actions to rollback.")
            return False
            
        last_action = self.action_history[-1]
        if not last_action.get("backups"):
            self.logger.warning("No backups available for the last action. Rollback impossible.")
            return False
            
        try:
            for original, backup in last_action["backups"]:
                shutil.copy2(backup, original)
                self.logger.info(f"Restored {original} from {backup}")
            
            self.logger.info("Rollback completed successfully.")
            return True
        except Exception as e:
            self.logger.critical(f"Rollback FAILED: {e}")
            return False

    def get_history(self):
        return self.action_history
