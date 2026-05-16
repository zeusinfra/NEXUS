# NEXUS Configs

This directory contains configuration files for the NEXUS system, including the
organizational runtime introduced for persistent supervised autonomy.

## Organizational Runtime

Primary files:

- `nexus.toml`: daemon, runtime, memory, agents, observer, and interface paths.
- `permissions.toml`: guarded execution defaults, approval requirements, and
  destructive command hints.
- `systemd/nexus-organization.service`: user-level systemd unit template.

The runtime is intentionally local-first. It writes state under `runtime/`,
memory under `memory/`, and logs under `logs/` unless overridden in TOML or the
environment.

Useful commands:

```bash
./bin/nexus org health
./bin/nexus org memory-status
./bin/nexus org systemd-plan
./bin/nexus org systemd-unit
./bin/nexus org systemd-install --write
```

The systemd installer is guarded:

- `systemd-plan` only reports what would happen.
- `systemd-install` does not write unless `--write` is present.
- `systemd-control` does not call `systemctl` unless `--execute` is present.

## Permission Defaults

The permission layer expects every command to be proposed and audited. Approval
and execution are separate steps:

```bash
./bin/nexus org propose-command --reason "inspect python" -- python3 --version
./bin/nexus org approve-command <proposal_id> --approved-by operator
./bin/nexus org execute-command <proposal_id> --agent operator
```

Destructive or privileged actions must include visible risk, impact, and
rollback context before the operator approves them.

## SSL Keys
The following files are **local fixtures** used for development and local testing only:
- `test-key.pem`
- `test-cert.pem`

**Do not use these keys in production.**

For real local SSL, you can provide your own `key.pem` and `cert.pem` in this directory (they are ignored by git).
