
import os
import shutil
import subprocess
import json
import logging
import shlex
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from zeus_core.command_policy import validate_command
from zeus_core.tools import ToolError

class SimulationLayer:
    """
    PHASE 4: Simulation Layer.
    Predicts outcomes by executing actions in a shadow environment.
    """
    def __init__(self, blackboard):
        self.blackboard = blackboard
        self.shadow_root = Path("/tmp/zeus_shadow")
        self.logger = logging.getLogger("ZEUS_SIMULATOR")
        self._setup_shadow_env()

    def _setup_shadow_env(self):
        """Ensures the shadow environment directory exists."""
        try:
            if not self.shadow_root.exists():
                self.shadow_root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create shadow env: {e}")

    def _prepare_shadow_files(self, target_paths: list):
        """Copies target files to the shadow environment for isolated testing."""
        for path in target_paths:
            try:
                src = Path(path)
                if src.exists() and src.is_file():
                    dest = self.shadow_root / src.name
                    shutil.copy2(src, dest)
            except Exception as e:
                self.logger.warning(f"Could not copy {path} to shadow: {e}")

    def simulate(self, command: str, files: list = None) -> Dict[str, Any]:
        """
        Simulates a command execution in the shadow environment.
        Returns a confidence score and the result.
        """
        if files:
            self._prepare_shadow_files(files)

        # Redirect command to run inside shadow root
        # This is a simplified simulation: executing in /tmp/zeus_shadow
        try:
            tokens = shlex.split(command)
            validate_command(command, tokens, confirmed=False)
            result = subprocess.run(
                tokens,
                cwd=str(self.shadow_root), 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            success = result.returncode == 0
            output = result.stdout
            error = result.stderr
            
            # Confidence calculation as per PLAN v3.0
            # confidence = (success * 0.4) + (no_errors * 0.3) + (low_diff * 0.2) + (performance_ok * 0.1)
            score = 0.0
            if success: score += 0.4
            if not error: score += 0.3
            # Simplified diff: if we have output but no error, we consider it low diff/ok for now
            if success and output: score += 0.3 # Combining low_diff and performance_ok
            
            return {
                "success": success,
                "confidence": score,
                "output": output,
                "error": error,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "confidence": 0.0, "error": "Simulation Timeout", "output": ""}
        except ToolError as e:
            return {"success": False, "confidence": 0.0, "error": str(e), "output": "", "blocked": True}
        except Exception as e:
            return {"success": False, "confidence": 0.0, "error": str(e), "output": ""}

    def cleanup(self):
        """Wipes the shadow environment."""
        try:
            shutil.rmtree(self.shadow_root)
            self._setup_shadow_env()
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
