"""
ZEUS Cognitive Core — Self-Healing Infrastructure.

Monitors system logs and health metrics to detect repeated failures,
proposing and applying autonomous fixes where safe.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from zeus_core.observability import get_logger, log_event
from zeus_core.core_system import call_cloud_llm
from zeus_core.command_policy import validate_command

logger = get_logger("zeus.cognitive.self_healing")


@dataclass
class HealingProposal:
    issue: str
    rationale: str
    commands: List[str]
    risk: str  # "low", "medium", "high"


class SelfHealingEngine:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self.log_path = os.getenv("ZEUS_LOG_PATH", "/var/log/zeus.log")

    def scan_for_issues(self) -> List[str]:
        """Reads recent logs to find error patterns."""
        if not os.path.exists(self.log_path):
            return []

        try:
            # Read last 100 lines
            with open(self.log_path, "r") as f:
                lines = f.readlines()[-100:]

            errors = [
                line
                for line in lines
                if "ERROR" in line or "CRITICAL" in line or "Exception" in line
            ]
            return errors
        except Exception as e:
            logger.error(f"Error scanning logs: {e}")
            return []

    def propose_fix(self, error_sample: List[str]) -> Optional[HealingProposal]:
        """Uses LLM to analyze errors and suggest a fix."""
        if not error_sample:
            return None

        sample_text = "\n".join(error_sample[:10])
        system_prompt = (
            "Você é o SELF-HEALING ENGINE do ZEUS. Analise os erros de log fornecidos e "
            "proponha uma solução técnica (comandos shell) para resolver o problema. "
            "Se o erro for comum (permissão, arquivo ausente, dependência), seja direto. "
            "Retorne em formato JSON: { 'issue': '...', 'rationale': '...', 'commands': [...], 'risk': 'low/medium/high' }"
        )
        user_prompt = f"Erros detectados:\n{sample_text}"

        try:
            import json

            response = call_cloud_llm(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            # Extract JSON from response
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if not match:
                return None

            data = json.loads(match.group(0))
            return HealingProposal(
                issue=data.get("issue", "Unknown"),
                rationale=data.get("rationale", ""),
                commands=data.get("commands", []),
                risk=data.get("risk", "medium"),
            )
        except Exception as e:
            logger.error(f"Error proposing fix: {e}")
            return None

    def apply_fix(self, proposal: HealingProposal) -> bool:
        """Applies a fix if it is low risk or confirmed."""
        if proposal.risk != "low":
            log_event(logger, 30, "healing_fix_skipped_risk", risk=proposal.risk)
            return False

        log_event(logger, 20, "applying_healing_fix", issue=proposal.issue)
        success = True
        for cmd in proposal.commands:
            try:
                tokens = shlex.split(cmd)
                validate_command(cmd, tokens, confirmed=False)
                subprocess.run(
                    tokens, check=True, capture_output=True, text=True, timeout=30
                )
            except Exception as e:
                logger.error(f"Failed to apply healing command '{cmd}': {e}")
                success = False
                break
        return success
