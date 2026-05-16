# NEXUS TUI

Terminal operations center for the NEXUS organizational runtime.

This first slice consumes real state through:

```bash
python -m nexus_core.organization ...
```

Views:

- Overview: daemon status and memory counters.
- Agents: latest continuous-agent ticks.
- Approvals: pending command approvals.
- Runtime: latest runtime command events.
- Verification: latest verification records.
- Observer: latest Linux context observations.

Operational rules:

- The TUI must not invent state; every row comes from `nexus_core.organization`.
- Approval and execution must remain separate actions.
- Destructive commands must show command, risk, impact, rollback, and evidence.
- Failures must remain visible instead of being collapsed into success text.

Run from the repository root:

```bash
./bin/nexus tui
```

The TUI needs Go installed because it is built with Bubble Tea. If Go is
missing, `./bin/nexus tui` exits with a clear message instead of pretending the
interface started.
