# NEXUS security model

NEXUS separates planning from execution. Cloud and local models may propose or
classify work, but real command execution remains local and must pass the
existing organizational security layer.

Command policy:

- `SAFE`: read-only diagnostics and limited inspection.
- `CAUTION`: package installs, service restarts and user config changes.
- `DANGEROUS`: `sudo`, `/etc`, ownership/mode changes, destructive file moves.
- `BLOCKED`: destructive disk operations and root-wide deletion patterns.

Rules:

- `sudo` requires explicit approval.
- destructive commands are blocked by default.
- real executions must capture stdout, stderr, exit code and duration.
- approved executions must pass through a structured execution plan.
- resource budgets may cap or block execution before a process starts.
- completed work must have verification evidence before it can be treated as
  done.
- failed executions must be diagnosed and persisted as incidents, not hidden.
- logs must not hide failures.
- API keys are read from environment files such as `/etc/nexus/nexus.env`.

The hybrid model router sends critical work to the `gemma4:31b-cloud` route for
strategic review and marks it as approval-required. The cloud route never
executes a command directly.

## Evidence and replay

The runtime persists:

- approval metadata and risk assessment;
- execution plan and per-step status;
- stdout/stderr paths and tails;
- exit code, duration and command status;
- verification result and evidence;
- self-healing diagnostic when a command fails;
- action replay timeline for command/task audit.

The core invariant is: NEXUS cannot honestly claim an action is done without
execution evidence and verification state.

Architecture overview: [FLOWCHART.md](FLOWCHART.md).
