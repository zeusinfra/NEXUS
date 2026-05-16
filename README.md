# NEXUS by Zeus Protocol

[![Enterprise Stability](https://img.shields.io/badge/Status-Enterprise--Grade-blue.svg)](https://zeusprotocol.cloud)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Website](https://img.shields.io/badge/Official-zeusprotocol.cloud-0052FF.svg)](https://zeusprotocol.cloud)

NEXUS is the flagship **Cognitive Operating Layer** developed by **Zeus Protocol**. Engineered for mission-critical Linux environments, it provides a persistent, verifiable, and autonomous organizational engine that transforms standard workstations into intelligent operational centers.

## 🏛️ Corporate Vision

At Zeus Protocol, we believe in **Local-First Autonomy**. NEXUS is designed to bridge the gap between high-level cognitive planning and real-world system execution. It operates as a structured organization within your OS: agents plan, review, observe, and execute through an auditable, policy-driven runtime.

The NEXUS operational contract is built on absolute transparency:
**Objective → Strategic Planning → Verified Execution → Validation → Evidence → Persistent Memory**

---

## 🚀 Core Infrastructure

### 1. Autonomous Organizational Engine
*   **Organizational Daemon**: A high-availability persistent runtime managing the system event bus, global blackboard, and agent registry.
*   **Swarm Orchestration**: Advanced multi-agent coordination (CEO, Planner, Guardian, etc.) designed for continuous, supervised task execution.

### 2. Enterprise Governance & Security
*   **Policy Enforcement**: Granular permission gates separating command proposal, multi-stage approval, and execution.
*   **Verifiable Runtime**: Every action is tracked with full artifact capture (stdout/stderr), cryptographic-ready command IDs, and mandatory verification checks.
*   **Security Boundary**: Local-first architecture ensuring that mission-critical data remains within your private infrastructure.

### 3. Cognitive Observability
*   **Enterprise Dashboard (Iced GUI)**: A high-fidelity Rust-based command center providing real-time telemetry, swarm interaction monitoring, and incident management.
*   **Organizational Memory**: High-performance SQLite-backed ledger for decisions, summaries, and agent state transitions.
*   **Operational HUD**: Real-time system health and neural metrics visualization.

---

## 📂 Repository Architecture

| Component | Description |
| :--- | :--- |
| `nexus_core/` | Core cognitive orchestration and security protocols. |
| `nexus_core/organization/` | The persistent daemon and swarm management layer. |
| `nexus-iced/` | Primary Enterprise Command Center GUI (Rust/Iced). |
| `core-rust/` | High-performance system bridges and sensory modules. |
| `apps/` | API backend and cognitive entrypoints. |
| `bin/` | Unified enterprise launcher for the NEXUS ecosystem. |

---

## 🛠️ Deployment & Operations

### System Requirements
NEXUS is optimized for modern Linux distributions (Debian, Ubuntu, Mint, Fedora).
*   **Runtime**: Python 3.10+ & Rust Stable.
*   **Dependencies**: `build-essential`, `libudev-dev`, `python3-dev`.

### Standard Installation
```bash
git clone https://github.com/zeusinfra/NEXUS.git
cd NEXUS
./scripts/bootstrap.sh
source .venv/bin/activate
```

### Initializing the Command Center
To launch the primary enterprise interface:
```bash
./bin/nexus
```

For server-only operations or organizational management:
```bash
./bin/nexus org run
./bin/nexus org health
```

---

## ⚖️ Governance and Compliance

Zeus Protocol maintains strict standards for autonomy and security.
*   **Auditability**: Full ledger of every command proposed and executed.
*   **Risk Mitigation**: Rollback guidance and impact assessment integrated into every operational proposal.
*   **Incident Management**: Real-time monitoring of verifications and system incidents.

---

## 🌐 Connect with Zeus Protocol

*   **Official Website**: [zeusprotocol.cloud](https://zeusprotocol.cloud)
*   **Developer Documentation**: [docs.zeusprotocol.cloud](https://zeusprotocol.cloud/docs)
*   **Support & Enterprise Inquiry**: [contact@zeusprotocol.cloud](mailto:contact@zeusprotocol.cloud)

---

### 📄 License
NEXUS is released under the MIT License. Copyright © 2026 Zeus Protocol. All rights reserved.
