# ZEUS Rust Migration Plan

Updated: 2026-05-10

## Objective

Improve ZEUS stability, speed, observability, and safety by moving deterministic
system components to Rust while keeping Python where it is strongest: LLM
orchestration, FastAPI surfaces, integrations, and rapid iteration.

This is a selective migration, not a rewrite. Every migrated component must keep
Python compatibility until tests prove parity.

## Migration Rules

1. Preserve current behavior before optimizing it.
2. Keep Python as the orchestration layer during migration.
3. Expose Rust through PyO3 modules or small local services with stable JSON
   contracts.
4. Add parity tests before switching runtime defaults.
5. Keep privileged execution behind approval gates and audit logs.
6. Never migrate secrets, tokens, or raw user data handling without explicit
   privacy review.

## Keep In Python

- LLM routing and provider handling.
- FastAPI routes and websocket/realtime UI glue.
- Notion, Linear, Obsidian, browser, voice, and OCR integrations.
- Prompt assembly and conversational policy text.
- High-level agent orchestration and UX feedback.
- Default desktop UX: Cinnamon applet plus GTK4 chat. The Hermes-style TUI is
  standby and should not replace GTK unless it reaches parity.

## Move To Rust First

### Phase 1: Policy and Sensors

Target modules:

- `zeus_core.command_policy`
- `zeus_core.diagnostics`
- `apps.web_gui.get_os_snapshot`
- `zeus_core.path_filters`

Rust modules already present:

- `core-rust/zeus_policy`
- `core-rust/zeus_sensors`

Expected benefits:

- Safer command classification.
- Faster process/system snapshots.
- Less Python `psutil` overhead in frequent loops.
- A single policy engine shared by chat actions, cognitive execution, and
  RootDaemon planning.

Acceptance criteria:

- Python and Rust command-policy decisions match on the existing test corpus.
- `rm`, `dd`, `mkfs`, reboot/shutdown, user/group changes, mount/umount, and
  shell control remain blocked in guarded mode.
- System metrics endpoint remains backward compatible.

### Phase 2: Memory Hot Paths

Target modules:

- `zeus_core.vector_memory`
- `zeus_core.memory_manager`
- cognitive memory compression routines

Rust modules already present:

- `core-rust/zeus_memory`
- `core-rust/zeus_synapse`

Expected benefits:

- Faster vector similarity search.
- More predictable memory persistence.
- Reduced CPU load during event bursts and sync cycles.

Acceptance criteria:

- Existing JSON/SQLite data is readable without destructive migration.
- Similarity search returns equivalent top-k ordering within tolerance.
- Memory save/load has rollback or backup.

### Phase 3: Cognitive Scoring and Planning Kernels

Target modules:

- `zeus_core.cognitive.priority_orchestrator`
- deterministic parts of `planner`, `simulator`, and `attention_engine`

Rust modules already present:

- `core-rust/zeus_cognitive`
- `core-rust/zeus_state`
- `core-rust/zeus_patterns`

Expected benefits:

- More predictable goal scoring.
- Better concurrency under load.
- Stronger typed boundaries for risk and plan state.

Acceptance criteria:

- Rust scoring produces explainable decisions.
- Python keeps final orchestration and human-facing summaries.
- High-risk goals still require approval.

### Phase 4: RootDaemon Hardening

Target modules:

- `zeus_core.security.root_daemon`
- backup/audit helpers
- privileged command classifier

Rust modules already present:

- `core-rust/zeus_security`
- `core-rust/zeus_policy`

Expected benefits:

- Smaller privileged surface.
- Better typed protocol validation.
- Stronger file/path handling.

Acceptance criteria:

- Socket protocol remains compatible.
- Audit log schema remains compatible.
- Forbidden commands stay impossible even in high-autonomy profiles.

### Phase 5: Event Pipeline and File Watchers

Target modules:

- Python event batching hot paths.
- watcher coordination.
- filesystem mirror path scanning.

Rust modules already present:

- `watcher_rs`
- `core-rust/zeus_sync`
- `core-rust/zeus_sensors`

Expected benefits:

- Lower event latency.
- Less CPU during filesystem bursts.
- Better backpressure.

Acceptance criteria:

- Websocket event payloads remain compatible.
- Overflow behavior remains bounded and observable.
- Runtime noise filters remain equivalent.

## Current Risks Found

- `apps.web_gui` is doing too many jobs in one module: API routes, telemetry,
  memory, chat, vision, voice, lifecycle, and sync orchestration.
- Rust policy exists but is less complete than the Python policy.
- `ZEUS_AUTONOMY_LEVEL=FULL` changes test expectations; parity tests should run
  in `GUARDED` and `FULL`.
- Several Rust crates expose useful kernels, but the Python fallback remains the
  source of truth in many places.

## Recommended Next Step

Start with Phase 1:

1. Expand `core-rust/zeus_policy` to match Python command policy.
2. Add parity tests that compare Python and Rust decisions.
3. Make Python use Rust policy when available, with clear fallback logging.
4. Move `get_os_snapshot` toward `zeus_sensors` once sensor payload parity is
   tested.

This improves all agents indirectly because every agent uses the same safer and
faster command/sensor substrate.

## Interface Posture

- GTK4/Libadwaita chat remains the default operator console.
- `bin/zeus-chat` launches GTK by default.
- `./bin/zeus tui` launches the Cyber TUI terminal surface.
- Rust migration work should not depend on replacing the GTK desktop flow.

## Phase 1 Progress

- 2026-05-10: `core-rust/zeus_policy` expanded to cover the Python command
  policy surface: autonomy level, allowlist, absolute blocklist, shell-control
  detection, risky interpreter flags, package subcommands, and confirmation
  requirements.
- 2026-05-10: Python loader now uses the local Rust extension from
  `core-rust/target/release/libzeus_policy.so` when the package is not installed
  globally.
- 2026-05-10: Added Rust unit tests and Python parity tests for guarded policy
  decisions.
- 2026-05-10: `core-rust/zeus_sensors` now exposes a typed OS snapshot JSON
  covering CPU cores, CPU average, RAM, root disk usage, pressure, and top
  processes.
- 2026-05-10: Python now loads `libzeus_sensors.so` locally when available and
  `apps.web_gui.get_os_snapshot` uses Rust first with `psutil` fallback.
