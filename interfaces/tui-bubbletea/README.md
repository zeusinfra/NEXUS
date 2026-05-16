# NEXUS Operations Center (TUI)

The **NEXUS Operations Center** is a high-efficiency terminal user interface (TUI) designed for the professional operator. Built using Go and the Bubble Tea framework, it provides a streamlined view into the **Zeus Protocol** organizational runtime.

## 🏛️ Operational Overview

This interface is intended for environments where low-latency terminal access is preferred over the full graphical Command Center. It connects directly to the NEXUS organizational daemon to provide:
*   **Real-time Swarm Status**: Monitoring of agent tasks and strategic planning.
*   **Command Ledger Visibility**: Auditing of proposed and executed actions.
*   **System Health Telemetry**: Live heartbeat monitoring of the cognitive operating layer.

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

---
Developed by **Zeus Protocol**. For enterprise terminal solutions, visit [zeusprotocol.cloud](https://zeusprotocol.cloud).
