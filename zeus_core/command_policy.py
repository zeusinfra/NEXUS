from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from zeus_core.observability import get_logger, log_event
from zeus_core.tools import ToolError


READ_COMMANDS = {"ls", "pwd", "echo", "cat", "sed", "rg", "find", "wc", "git", "python3", "node", "npm", "cargo"}
WRITE_COMMANDS = {"cp", "mv", "mkdir", "touch", "chmod", "chown", "git"}
BLOCKED_COMMANDS = {
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "passwd",
    "usermod",
    "useradd",
    "groupadd",
    "visudo",
    "mount",
    "umount",
    "rm",
}
SHELL_CONTROL_TOKENS = {"|", "&&", "||", ";", ">", ">>", "<", "$(", "`"}


logger = get_logger("zeus.command_policy")


@dataclass(frozen=True)
class CommandDecision:
    exe: str
    category: str
    requires_confirmation: bool


def _configured_allowlist() -> set[str]:
    return {
        item.strip()
        for item in os.getenv(
            "ZEUS_CMD_ALLOWLIST",
            "ls,pwd,echo,cat,sed,rg,find,wc,python3,node,npm,cargo,git",
        ).split(",")
        if item.strip()
    }


def _contains_shell_control(command: str) -> bool:
    return any(token in command for token in SHELL_CONTROL_TOKENS)


def classify_command(tokens: list[str]) -> CommandDecision:
    exe = Path(tokens[0]).name if tokens else ""
    if exe in WRITE_COMMANDS:
        return CommandDecision(exe=exe, category="write", requires_confirmation=True)
    return CommandDecision(exe=exe, category="read", requires_confirmation=False)


def validate_command(command: str, tokens: list[str], *, confirmed: bool = False) -> CommandDecision:
    if not tokens:
        raise ToolError("Comando inválido.")

    decision = classify_command(tokens)
    allowlist = _configured_allowlist()

    try:
        if _contains_shell_control(command):
            raise ToolError("Encadeamento/redirecionamento de shell bloqueado em cmd_control.")
        if decision.exe not in allowlist:
            raise ToolError(f"Comando fora da allowlist: {decision.exe}")
        if decision.exe in BLOCKED_COMMANDS:
            raise ToolError(f"Comando bloqueado por segurança: {decision.exe}")
        if decision.requires_confirmation and not confirmed:
            raise ToolError(f"Comando de escrita requer confirmação explícita: {decision.exe}")
        log_event(
            logger,
            20,
            "command_policy_allowed",
            command=command,
            exe=decision.exe,
            category=decision.category,
            confirmed=confirmed,
        )
        return decision
    except ToolError as e:
        log_event(
            logger,
            30,
            "command_policy_rejected",
            command=command,
            exe=decision.exe,
            category=decision.category,
            confirmed=confirmed,
            reason=str(e),
        )
        raise
