# NEXUS Runtime TUI

The **NEXUS Runtime TUI** is a high-efficiency terminal interface designed for operators who need quick access to runtime state without opening the graphical conversational UI. Built using Go and the Bubble Tea framework, it provides a streamlined view into the **Zeus Protocol** organizational runtime.

## 🏛️ Operational Overview

This interface is intended for environments where low-latency terminal access is preferred over the full graphical assistant. It connects directly to the NEXUS organizational daemon to provide:
*   **Real-time Swarm Status**: Monitoring of agent tasks and strategic planning.
*   **Command Ledger Visibility**: Auditing of proposed and executed actions.
*   **System Health Telemetry**: Live heartbeat monitoring of the cognitive operating layer.
*   **Execution Replay**: Command and task timelines reconstructed from plans, runtime events and verification evidence.
*   **Workspace Context**: Project traits detected by the organizational daemon, such as Rust, Iced, Axum, SQLx and test coverage.

## 🛠️ Build and Deployment

### Requirements
*   **Go 1.21+**
*   Active **NEXUS Organizational Daemon** running on the host.

### Building the TUI
```bash
cd interfaces/tui-bubbletea
go build -o nexus-tui
```

### Usage
```bash
./nexus-tui
```
Alternatively, use the unified launcher from the project root:
```bash
./bin/nexus tui
```

The same runtime data can be inspected through the CLI:

```bash
./bin/nexus org workspace-context
./bin/nexus org execution-plans
./bin/nexus org replay-command cmd_...
```

---
Developed by **Zeus Protocol**. For enterprise terminal solutions, visit [zeusprotocol.cloud](https://zeusprotocol.cloud).
