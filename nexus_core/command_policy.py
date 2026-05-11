from __future__ import annotations

import os
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from nexus_core.observability import get_logger, log_event
from nexus_core.tools import ToolError


READ_COMMANDS = {
    "ls",
    "pwd",
    "echo",
    "cat",
    "sed",
    "rg",
    "find",
    "wc",
    "git",
    "python3",
    "node",
    "npm",
    "cargo",
    "df",
    "free",
    "uptime",
    "lscpu",
    "lsblk",
    "ip",
    "ss",
    "top",
    "htop",
    "neofetch",
    "date",
    "cal",
    "which",
    "whereis",
    "type",
    "env",
    "printenv",
}
WRITE_COMMANDS = {
    "cp",
    "mv",
    "mkdir",
    "touch",
    "chmod",
    "chown",
    "git",
    "rm",
    "apt",
    "pip",
    "pip3",
    "npm",
    "cargo",
    "systemctl",
}
CONFIRMATION_ONLY_COMMANDS = {
    "python3",
    "python",
    "node",
    "npm",
    "npx",
    "cargo",
    "rm",
    "apt",
    "systemctl",
}

BLOCKED_COMMANDS = {
    "rm",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "passwd",
    "usermod",
    "useradd",
    "userdel",
    "groupadd",
    "groupmod",
    "groupdel",
    "visudo",
    "chpasswd",
    "mount",
    "umount",
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
    "npm": {
        "exec",
        "explore",
        "install",
        "i",
        "link",
        "rebuild",
        "run",
        "run-script",
        "start",
        "test",
    },
    "npx": {"*"},
    "cargo": {"bench", "build", "clippy", "fix", "install", "publish", "run", "test"},
    "apt": {
        "install",
        "remove",
        "purge",
        "upgrade",
        "dist-upgrade",
        "autoremove",
        "full-upgrade",
    },
    "systemctl": {
        "start",
        "stop",
        "restart",
        "enable",
        "disable",
        "mask",
        "unmask",
        "reload",
    },
}


logger = get_logger("nexus.command_policy")


def _load_rust_policy():
    local_extension = (
        Path(__file__).resolve().parents[1]
        / "core-rust"
        / "target"
        / "release"
        / "libnexus_policy.so"
    )
    if local_extension.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                "nexus_policy", local_extension
            )
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.CommandPolicyRust()
        except Exception as exc:
            log_event(logger, 30, "rust_policy_local_load_failed", error=str(exc))

    try:
        from nexus_policy import CommandPolicyRust

        return CommandPolicyRust()
    except Exception as exc:
        log_event(logger, 30, "rust_policy_load_failed", error=str(exc))
        return None


_RUST_POLICY = _load_rust_policy()
RUST_POLICY_AVAILABLE = _RUST_POLICY is not None


@dataclass(frozen=True)
class CommandDecision:
    exe: str
    category: str
    requires_confirmation: bool


def _configured_allowlist() -> set[str]:
    return {
        item.strip()
        for item in os.getenv(
            "NEXUS_CMD_ALLOWLIST",
            "ls,pwd,echo,cat,sed,rg,find,wc,python3,node,npm,cargo,git,systemctl,apt,pip,pip3,df,free,uptime,ip,ss,top,htop",
        ).split(",")
        if item.strip()
    }


def _contains_shell_control(command: str) -> bool:
    return any(token in command for token in SHELL_CONTROL_TOKENS)


def classify_command(tokens: list[str]) -> CommandDecision:
    exe = Path(tokens[0]).name if tokens else ""
    autonomy = os.getenv("NEXUS_AUTONOMY_LEVEL", "GUARDED").upper()

    if autonomy == "FULL":
        return CommandDecision(
            exe=exe, category="autonomous", requires_confirmation=False
        )

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


def validate_command(
    command: str, tokens: list[str], *, confirmed: bool = False
) -> CommandDecision:
    if not tokens:
        raise ToolError("Comando inválido.")

    decision = classify_command(tokens)
    allowlist = _configured_allowlist()
    autonomy = os.getenv("NEXUS_AUTONOMY_LEVEL", "GUARDED").upper()

    try:
        if autonomy != "FULL" and _contains_shell_control(command):
            raise ToolError(
                "Encadeamento/redirecionamento de shell bloqueado em cmd_control."
            )

        if decision.exe not in allowlist and autonomy != "FULL":
            raise ToolError(f"Comando fora da allowlist: {decision.exe}")

        if decision.exe in BLOCKED_COMMANDS:
            # Blocklist is absolute except maybe in some extreme cases, but per requirement it should never be automatic.
            raise ToolError(f"Comando bloqueado por segurança: {decision.exe}")

        if autonomy != "FULL" and decision.requires_confirmation and not confirmed:
            raise ToolError(f"Comando requer confirmação explícita: {decision.exe}")

        if _RUST_POLICY:
            ok, reason = _RUST_POLICY.validate_command(command, tokens, confirmed)
            if not ok:
                raise ToolError(reason)

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
