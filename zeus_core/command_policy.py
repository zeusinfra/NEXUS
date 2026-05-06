from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from zeus_core.observability import get_logger, log_event
from zeus_core.tools import ToolError


READ_COMMANDS = {"ls", "pwd", "echo", "cat", "sed", "rg", "find", "wc", "git", "python3", "node", "npm", "cargo"}
WRITE_COMMANDS = {"cp", "mv", "mkdir", "touch", "chmod", "chown", "git"}
CONFIRMATION_ONLY_COMMANDS = {"python3", "python", "node", "npm", "npx", "cargo"}
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
RISKY_INTERPRETER_FLAGS = {
    "python": {"-c", "-m"},
    "python3": {"-c", "-m"},
    "node": {"-e", "--eval", "-p", "--print", "-r", "--require"},
}
SAFE_INTERPRETER_ARGS = {
    "python": {"--version", "-V"},
    "python3": {"--version", "-V"},
    "node": {"--version", "-v"},
}
RISKY_PACKAGE_SUBCOMMANDS = {
    "npm": {"exec", "explore", "install", "i", "link", "rebuild", "run", "run-script", "start", "test"},
    "npx": {"*"},
    "cargo": {"bench", "build", "clippy", "fix", "install", "publish", "run", "test"},
}


logger = get_logger("zeus.command_policy")

try:
    from zeus_policy import CommandPolicyRust
    RUST_POLICY_AVAILABLE = True
    _RUST_POLICY = CommandPolicyRust()
except ImportError:
    RUST_POLICY_AVAILABLE = False
    _RUST_POLICY = None


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
    if _requires_confirmation_for_args(exe, tokens[1:]):
        return CommandDecision(exe=exe, category="exec", requires_confirmation=True)
    return CommandDecision(exe=exe, category="read", requires_confirmation=False)


def _requires_confirmation_for_args(exe: str, args: list[str]) -> bool:
    if exe in RISKY_INTERPRETER_FLAGS:
        risky_flags = RISKY_INTERPRETER_FLAGS[exe]
        safe_args = SAFE_INTERPRETER_ARGS.get(exe, set())
        return bool(args) and (
            any(arg in risky_flags for arg in args)
            or any(arg not in safe_args for arg in args)
        )

    risky_subcommands = RISKY_PACKAGE_SUBCOMMANDS.get(exe)
    if risky_subcommands:
        if "*" in risky_subcommands:
            return True
        first_arg = next((arg for arg in args if not arg.startswith("-")), "")
        return first_arg in risky_subcommands

    return exe in CONFIRMATION_ONLY_COMMANDS and bool(args)


def validate_command(command: str, tokens: list[str], *, confirmed: bool = False) -> CommandDecision:
    if not tokens:
        raise ToolError("Comando inválido.")

    if _RUST_POLICY:
        ok, reason = _RUST_POLICY.validate_command(command, tokens, confirmed)
        if not ok:
            raise ToolError(reason)
        # Se passou no Rust, fazemos o de-para para CommandDecision do Python
        decision = classify_command(tokens)
        return decision

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
