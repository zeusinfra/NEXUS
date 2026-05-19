# Architecture decisions

This document records current product decisions so implementation, packaging and
documentation stay aligned.

## ADR-001: Python FastAPI remains the runtime backend

Status: accepted

`apps/web_gui.py` is the current product backend. It owns the live FastAPI
routes, websocket handlers, cognitive state wiring, memory calls, voice/vision
API and static web surface.

The Rust `backend/` crate is kept as an experimental Axum lab. It can be built,
checked and packaged as an optional binary, but it is not the default runtime
backend until route parity, migration tests and packaging behavior are proven.

Consequence: backend refactors must preserve Python route behavior first, then
extract modules by domain.

## ADR-002: Rust is used for GUI and focused local services

Status: accepted

Rust owns the Iced GUI (`nexus-iced`), external watcher (`watcher_rs`) and memory
service (`core-rust/nexus_memory`). These are long-running local components
where compiled binaries make startup more predictable.

Consequence: Debian runtime must ship compiled Rust binaries and must not call
`cargo run` after installation.

## ADR-003: The GUI is a first-class runtime entrypoint

Status: accepted

Running `nexus` with no command starts the desktop GUI and ensures the Python
backend is available. Server-only operation remains available through
`nexus server` and the organization daemon through `nexus org run`.

Consequence: the package must include `nexus-iced`, `watcher_rs`,
`memory_service`, Python backend modules, static UI assets and root-level Python
modules imported by the backend.

## ADR-004: The organization daemon owns supervised execution

Status: accepted

Real command execution should flow through approval, execution planning, budget
checks, evidence capture, verification, replay and memory persistence.

Consequence: modules such as `simulation_layer.py`, `recovery_engine.py` and
`actions_registry.py` should integrate into the approval/execution flow instead
of becoming parallel execution paths.

## ADR-005: Sensing and autonomous features are opt-in

Status: accepted

Voice sensing, browser sensing, autonomous tasks, ASR, OCR and second-brain sync
must stay disabled by default unless the operator explicitly enables them.

Consequence: `nexus health` can report missing ASR/OCR tools, but absence of
`ffmpeg`, `faster_whisper` or `tesseract` should not break the base runtime.

## ADR-006: Generated artifacts are not source

Status: accepted

`dist/`, `.deb` files, SQLite WAL/SHM files, `test_db/` and real long-term
memory JSON are local/generated artifacts.

Consequence: these paths are ignored by Git and removed from version control.
Examples and templates remain versioned.
