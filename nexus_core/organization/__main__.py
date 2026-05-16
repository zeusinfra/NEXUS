from __future__ import annotations

import argparse
import json

from nexus_core.execution_protocol import ApprovalScope
from nexus_core.organization.config import load_org_config
from nexus_core.organization.daemon import (
    OrganizationalDaemon,
    run_daemon,
    status_payload,
)
from nexus_core.organization.health import (
    build_health_report,
    install_instructions,
    install_systemd_unit,
    render_systemd_user_unit,
    systemd_control,
    systemd_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="NEXUS organizational daemon")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run")
    sub.add_parser("status")
    sub.add_parser("health")
    sub.add_parser("systemd-unit")
    sub.add_parser("systemd-install-instructions")
    sub.add_parser("systemd-plan")

    systemd_install = sub.add_parser("systemd-install")
    systemd_install.add_argument("--write", action="store_true")
    systemd_install.add_argument("--unit-path", default=None)

    systemd_ctl = sub.add_parser("systemd-control")
    systemd_ctl.add_argument(
        "action",
        choices=[
            "daemon-reload",
            "enable",
            "disable",
            "start",
            "stop",
            "restart",
            "status",
        ],
    )
    systemd_ctl.add_argument("--execute", action="store_true")
    systemd_ctl.add_argument("--timeout-s", type=int, default=15)

    submit = sub.add_parser("submit")
    submit.add_argument("goal", nargs="+")
    submit.add_argument("--role", default=None)

    propose = sub.add_parser("propose-command")
    propose.add_argument("--cwd", default=None)
    propose.add_argument("--reason", default="")
    propose.add_argument("--requested-by", default="operator")
    propose.add_argument("shell_command", nargs=argparse.REMAINDER)

    approvals = sub.add_parser("approvals")
    approvals.add_argument("--status", default=None)

    memory_status = sub.add_parser("memory-status")
    memory_status.add_argument("--json", action="store_true")

    memory_tasks = sub.add_parser("memory-tasks")
    memory_tasks.add_argument("--status", default=None)
    memory_tasks.add_argument("--limit", type=int, default=20)

    memory_decisions = sub.add_parser("memory-decisions")
    memory_decisions.add_argument("--limit", type=int, default=20)

    memory_events = sub.add_parser("memory-events")
    memory_events.add_argument("--type", default=None)
    memory_events.add_argument("--limit", type=int, default=20)

    summarize = sub.add_parser("summarize-memory")
    summarize.add_argument("--scope", default="recent")
    summarize.add_argument("--limit", type=int, default=20)

    approve = sub.add_parser("approve-command")
    approve.add_argument("proposal_id")
    approve.add_argument("--approved-by", required=True)
    approve.add_argument(
        "--scope", choices=["once", "session-low-risk"], default="once"
    )
    approve.add_argument("--ttl-seconds", type=int, default=600)

    execute = sub.add_parser("execute-command")
    execute.add_argument("proposal_id")
    execute.add_argument("--timeout-s", type=int, default=30)
    execute.add_argument("--agent", default="runtime")

    runtime_events = sub.add_parser("runtime-events")
    runtime_events.add_argument("--command-id", default=None)
    runtime_events.add_argument("--limit", type=int, default=50)

    verifications = sub.add_parser("verifications")
    verifications.add_argument("--command-id", default=None)
    verifications.add_argument("--limit", type=int, default=50)

    sub.add_parser("observe")

    observations = sub.add_parser("observations")
    observations.add_argument("--limit", type=int, default=50)

    agent_ticks = sub.add_parser("agent-ticks")
    agent_ticks.add_argument("--role", default=None)
    agent_ticks.add_argument("--limit", type=int, default=50)

    sub.add_parser("tick-agents")

    args = parser.parse_args()
    command = args.command or "run"

    if command == "run":
        import asyncio

        asyncio.run(run_daemon(args.config))
        return

    if command == "status":
        _print(status_payload(args.config))
        return
    if command == "health":
        _print(build_health_report(load_org_config(args.config)).to_dict())
        return
    if command == "systemd-unit":
        print(render_systemd_user_unit(load_org_config(args.config)), end="")
        return
    if command == "systemd-install-instructions":
        _print(install_instructions(load_org_config(args.config)))
        return
    if command == "systemd-plan":
        _print(systemd_plan(load_org_config(args.config)))
        return
    if command == "systemd-install":
        from pathlib import Path

        _print(
            install_systemd_unit(
                load_org_config(args.config),
                write=args.write,
                unit_path=Path(args.unit_path).expanduser() if args.unit_path else None,
            )
        )
        return
    if command == "systemd-control":
        _print(
            systemd_control(
                args.action,
                execute=args.execute,
                timeout_s=args.timeout_s,
            )
        )
        return

    config = load_org_config(args.config)
    daemon = OrganizationalDaemon(config)
    read_only_commands = {
        "approvals",
        "memory-status",
        "memory-tasks",
        "memory-decisions",
        "memory-events",
        "runtime-events",
        "verifications",
        "observations",
        "agent-ticks",
    }
    daemon.initialize(record_event=command not in read_only_commands)

    if command == "submit":
        payload = daemon.submit_goal(" ".join(args.goal), role=args.role).__dict__
    elif command == "propose-command":
        if args.shell_command and args.shell_command[0] == "--":
            args.shell_command = args.shell_command[1:]
        payload = daemon.propose_command(
            " ".join(args.shell_command),
            cwd=args.cwd,
            reason=args.reason,
            requested_by=args.requested_by,
        )
    elif command == "approvals":
        payload = daemon.permissions.queue.list(status=args.status)
    elif command == "memory-status":
        payload = daemon.memory_status()
    elif command == "memory-tasks":
        payload = daemon.memory.list_tasks(status=args.status, limit=args.limit)
    elif command == "memory-decisions":
        payload = daemon.memory.list_decisions(limit=args.limit)
    elif command == "memory-events":
        payload = daemon.memory.list_events(event_type=args.type, limit=args.limit)
    elif command == "summarize-memory":
        payload = daemon.summarize_memory(scope=args.scope, limit=args.limit)
    elif command == "approve-command":
        scope = (
            ApprovalScope.SESSION_LOW_RISK
            if args.scope == "session-low-risk"
            else ApprovalScope.ONCE
        )
        payload = daemon.permissions.approve_command(
            args.proposal_id,
            approved_by=args.approved_by,
            approval_scope=scope,
            ttl_seconds=args.ttl_seconds,
        )
    elif command == "execute-command":
        import asyncio

        payload = asyncio.run(
            daemon.runtime.execute_approved(
                args.proposal_id, agent=args.agent, timeout_s=args.timeout_s
            )
        )
    elif command == "runtime-events":
        payload = daemon.memory.list_runtime_events(
            command_id=args.command_id, limit=args.limit
        )
    elif command == "verifications":
        payload = daemon.memory.list_verifications(
            command_id=args.command_id, limit=args.limit
        )
    elif command == "observe":
        payload = daemon.observe_once()
    elif command == "observations":
        payload = daemon.memory.list_observations(limit=args.limit)
    elif command == "tick-agents":
        payload = daemon.tick_agents_once()
    elif command == "agent-ticks":
        payload = daemon.memory.list_agent_ticks(agent_role=args.role, limit=args.limit)
    else:  # pragma: no cover - argparse prevents this branch
        raise SystemExit(f"Unknown command: {command}")
    _print(payload)


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
