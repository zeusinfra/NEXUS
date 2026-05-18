# NEXUS Configuration & Deployment

This directory contains the core configuration templates and systemd unit specifications for the **NEXUS Cognitive Operating Layer**.

## 🏛️ Configuration Management

The NEXUS environment is governed by professional-grade configuration standards defined by **Zeus Protocol**. Proper deployment ensures high availability and operational integrity of the organizational runtime.

### Contents
*   **systemd/**: Enterprise unit templates for managing the NEXUS daemon as a background service.
*   **templates/**: Standardized configuration files for agent roles and system policies.
*   Runtime safety is controlled through environment values such as `NEXUS_EXEC_CONCURRENT_LIMIT`, `NEXUS_EXEC_TIMEOUT_MAX_SEC`, `NEXUS_EXEC_CPU_SOFT_LIMIT`, `NEXUS_EXEC_RAM_SOFT_LIMIT`, and `NEXUS_EXEC_BLOCK_ON_RESOURCE_PRESSURE`.

## 🚀 Deployment Strategy

Zeus Protocol recommends deploying the organizational daemon via systemd for persistent operation. The unified NEXUS launcher provides helper commands to plan and install these units:

```bash
# Generate a deployment plan
./bin/nexus org systemd-plan

# Install and enable the unit
./bin/nexus org systemd-install --write
```

After deployment, verify the cognitive runtime state with:

```bash
./bin/nexus org workspace-context
./bin/nexus org execution-plans
./bin/nexus org incidents
```

For more information on enterprise deployment and scaling, visit the [Zeus Protocol Cloud](https://zeusprotocol.cloud).

---
Copyright © 2026 Zeus Protocol. All rights reserved.
