# NEXUS by Zeus Protocol

[![Enterprise Stability](https://img.shields.io/badge/Status-Enterprise--Grade-blue.svg)](https://zeusprotocol.cloud)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Website](https://img.shields.io/badge/Official-zeusprotocol.cloud-0052FF.svg)](https://zeusprotocol.cloud)

NEXUS is the flagship **Cognitive Operating Layer** developed by **Zeus Protocol**. Engineered for mission-critical Linux environments, it provides a persistent, verifiable, and autonomous organizational engine that transforms standard workstations into calm, conversational cognitive workspaces.

## 🏛️ Corporate Vision

At Zeus Protocol, we believe in **Local-First Autonomy**. NEXUS is designed to bridge the gap between high-level cognitive planning and real-world system execution. It operates as a structured organization within your OS: agents plan, review, observe, and execute through an auditable, policy-driven runtime.

The NEXUS operational contract is built on absolute transparency:
**Objective → Structured Plan → Budgeted Execution → Verification → Evidence → Replay → Persistent Memory**

---

## 🚀 Core Infrastructure

### 1. Autonomous Organizational Engine
*   **Organizational Daemon**: A high-availability persistent runtime managing the system event bus, global blackboard, and agent registry.
*   **Swarm Orchestration**: Advanced multi-agent coordination (CEO, Planner, Guardian, etc.) designed for continuous, supervised task execution.

### 2. Enterprise Governance & Security
*   **Policy Enforcement**: Granular permission gates separating command proposal, multi-stage approval, and execution.
*   **Verifiable Runtime**: Every action is tracked with full artifact capture (stdout/stderr), cryptographic-ready command IDs, and mandatory verification checks.
*   **Structured Execution Plans**: Approved actions are expanded into explicit steps such as approval validation, resource budget checks, execution, verification, and replay persistence.
*   **Action Replay**: Completed commands and tasks can be reconstructed as timelines for debugging, audit, and cognitive observability.
*   **Security Boundary**: Local-first architecture ensuring that mission-critical data remains within your private infrastructure.

### 3. Cognitive Observability
*   **Premium Conversational GUI (Rust/Iced)**: A ChatGPT/Claude-inspired assistant surface focused on clarity, low visual noise, and fast human interaction.
*   **Organizational Memory**: High-performance SQLite-backed ledger for decisions, summaries, agent state transitions, execution plans, verification evidence, and replays.
*   **Workspace Memory**: Project traits such as Rust, Iced, Axum, WebSocket architecture, SQLx, tests, and organization runtime are detected and persisted.
*   **Self-Healing Diagnostics**: Failed commands are classified and converted into safe recovery steps before the operator receives a final failure.
*   **Resource Governor**: Local autonomy is constrained by timeout, concurrency, CPU/RAM pressure, and token budgets.

---

## 📂 Repository Architecture

| Component | Description |
| :--- | :--- |
| `nexus_core/` | Core cognitive orchestration and security protocols. |
| `nexus_core/organization/` | The persistent daemon and swarm management layer. |
| `nexus-iced/` | Primary conversational GUI (Rust/Iced). |
| `core-rust/` | High-performance system bridges and sensory modules. |
| `apps/` | Primary Python FastAPI backend and cognitive entrypoints. |
| `backend/` | Experimental Rust/Axum backend prototype; not required for default runtime. |
| `bin/` | Unified enterprise launcher for the NEXUS ecosystem. |

> The runtime backend is currently Python FastAPI in `apps/web_gui.py`. The `backend/` Rust/Axum project is an experimental lab for future migration and is not required for normal development or package runtime.

---

## 🛠️ Deployment & Operations

### System Requirements
NEXUS is optimized for modern Linux distributions (Debian, Ubuntu, Mint, Fedora).
*   **Runtime**: Python 3.10+. The Debian package ships compiled Rust binaries.
*   **Build from source**: Rust Stable plus the normal native build toolchain.
*   **Dependencies**: `build-essential`, `libudev-dev`, `python3-dev`.

### Standard Installation
```bash
git clone https://github.com/zeusinfra/NEXUS.git
cd NEXUS
./scripts/bootstrap.sh
source .venv/bin/activate
```

### Initializing the Conversational Interface
To launch the primary conversational interface:
```bash
./bin/nexus
```

For server-only operations or organizational management:
```bash
./bin/nexus org run
./bin/nexus org health
```

### Verifiable Runtime Commands
The organizational runtime exposes the same evidence-first primitives used by
the GUI:

```bash
./bin/nexus org workspace-context
./bin/nexus org execution-plans
./bin/nexus org execution-steps --command-id cmd_...
./bin/nexus org replay-command cmd_...
./bin/nexus org replay-task task_...
```

### Hybrid LLM Product CLI
NEXUS now includes a Linux product CLI surface for hybrid local/cloud model
routing. The local path detects an existing Ollama installation and models
without installing or pulling anything automatically.

The strategic cloud route is `gemma4:31b-cloud` through the Ollama provider
configuration. It is the default model for complex and critical reasoning in
the product docs and default config.

```bash
./bin/nexus status
./bin/nexus health
./bin/nexus model status
./bin/nexus model list-local
./bin/nexus router explain "planejar pacote .deb com systemd"
```

Routing policy:

| Task class | Default route | Purpose |
| :--- | :--- | :--- |
| `simple` | Ollama local | quick answers, summaries, log classification |
| `normal` | Ollama local | lightweight offline reasoning |
| `complex` | `gemma4:31b-cloud` | architecture, package planning, deep debugging |
| `critical` | `gemma4:31b-cloud` + approval | sudo, systemd, `/etc`, destructive risk |

### Debian Package
Build a local `.deb` package:

```bash
make deb
make test-package
```

The package includes the Python FastAPI runtime, static UI assets and compiled
Rust binaries for `nexus-iced`, `watcher_rs`, `memory_service` and the optional
Rust backend lab binary. Installed runtime startup does not depend on
`cargo run`.

Install flow:

```bash
sudo apt install ./dist/nexus_0.1.5_amd64.deb
sudo nexus setup
sudo systemctl enable --now nexus
nexus status
```

See `docs/INSTALL.md`, `docs/PACKAGE.md`, `docs/ARCHITECTURE.md` and
`docs/RUNTIME.md` for the product layout, runtime paths and safety model. The
current architecture flowchart is in `docs/FLOWCHART.md`; implementation
decisions are tracked in `docs/ARCHITECTURE_DECISIONS.md`, and loose module
classification is tracked in `docs/MODULE_CLASSIFICATION.md`.

---

## ⚖️ Governance and Compliance

Zeus Protocol maintains strict standards for autonomy and security.
*   **Auditability**: Full ledger of every command proposed and executed.
*   **Risk Mitigation**: Rollback guidance and impact assessment integrated into every operational proposal.
*   **Replayability**: Commands and tasks can be replayed from persisted plans, runtime events, stdout/stderr artifacts, and verification records.
*   **Incident Management**: Real-time monitoring of verifications and system incidents.

---

## 🌐 Connect with Zeus Protocol

*   **Official Website**: [zeusprotocol.cloud](https://zeusprotocol.cloud)
*   **Developer Documentation**: [docs.zeusprotocol.cloud](https://zeusprotocol.cloud/docs)
*   **Support & Enterprise Inquiry**: WhatsApp +55 (12) 98247-4095

---

### 📄 License
NEXUS is released under the MIT License. Copyright © 2026 Zeus Protocol. All rights reserved.
