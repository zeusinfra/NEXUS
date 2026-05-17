from __future__ import annotations

import os
import re
from dataclasses import dataclass

from nexus_core.v4.types import AutonomyMode, RiskLevel


@dataclass(slots=True)
class RiskAssessment:
    level: RiskLevel
    reason: str
    intent: str


_DESTRUCTIVE_PATTERNS: list[tuple[re.Pattern, RiskLevel, str]] = [
    (
        re.compile(r"\brm\b.*\b-rf\b.*\b/\b"),
        RiskLevel.CRITICAL,
        "remoção recursiva do root",
    ),
    (
        re.compile(r"\bmkfs\b|\bdd\b\s+if="),
        RiskLevel.CRITICAL,
        "formatação/overwrite de disco",
    ),
    (
        re.compile(r"\bshutdown\b|\breboot\b|\bpoweroff\b"),
        RiskLevel.HIGH,
        "interrupção do sistema",
    ),
    (re.compile(r"\bsudo\b"), RiskLevel.HIGH, "elevação de privilégio"),
    (re.compile(r"\bchmod\b\s+777\b"), RiskLevel.HIGH, "permissão excessiva"),
    (re.compile(r"\bkill\b\s+-9\b"), RiskLevel.MEDIUM, "process kill forçado"),
]


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


class SemanticGuardian:
    def __init__(self, *, mode: AutonomyMode):
        self.mode = mode

    def assess_action(self, action: dict) -> RiskAssessment:
        """
        Action schema (v4):
        - {"type":"cmd","command":"..."}
        - {"type":"file","op":"write|move|delete|...","path":"...","content":"..."}
        """
        a_type = _normalize(str(action.get("type") or ""))
        if a_type == "cmd":
            cmd = _normalize(str(action.get("command") or ""))
            if not cmd:
                return RiskAssessment(RiskLevel.LOW, "comando vazio", "noop")
            for pat, lvl, why in _DESTRUCTIVE_PATTERNS:
                if pat.search(cmd):
                    return RiskAssessment(lvl, why, "command_execution")
            if any(
                tok in cmd
                for tok in ["apt ", "dnf ", "pacman ", "pip install", "curl ", "wget "]
            ):
                return RiskAssessment(
                    RiskLevel.MEDIUM,
                    "instalação/download pode alterar o sistema",
                    "package_or_network",
                )
            return RiskAssessment(RiskLevel.LOW, "comando comum", "command_execution")

        if a_type == "file":
            op = _normalize(str(action.get("op") or ""))
            path = _normalize(str(action.get("path") or ""))
            if op in {"delete", "rm"}:
                if (
                    path in {"/", "~", ""}
                    or path.startswith("/etc")
                    or path.startswith("/usr")
                ):
                    return RiskAssessment(
                        RiskLevel.CRITICAL, "deleção em path sensível", "file_delete"
                    )
                return RiskAssessment(
                    RiskLevel.MEDIUM, "deleção de arquivo", "file_delete"
                )
            if op in {"write", "move", "copy", "rename"} and (
                path.startswith("/etc") or path.startswith("/usr")
            ):
                return RiskAssessment(
                    RiskLevel.HIGH, "alteração em path sensível", "file_modify"
                )
            return RiskAssessment(RiskLevel.LOW, "operação de arquivo comum", "file_op")

        return RiskAssessment(RiskLevel.MEDIUM, "ação desconhecida", "unknown")

    def requires_confirmation(self, assessment: RiskAssessment) -> bool:
        if assessment.level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return True
        if self.mode == AutonomyMode.SAFE:
            return True
        if self.mode == AutonomyMode.DEV and assessment.level == RiskLevel.MEDIUM:
            return os.getenv("NEXUS_V4_CONFIRM_MEDIUM", "0").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        return False
