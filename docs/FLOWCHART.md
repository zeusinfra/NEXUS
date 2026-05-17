# NEXUS architecture flowchart

This diagram describes the current product direction: NEXUS as a Linux
installable Cognitive OS with hybrid local/cloud intelligence, supervised
execution, verification and organizational memory.

```mermaid
flowchart TD
    CEO[CEO / Operator / Beginner User] --> GUI[Rust Iced GUI]
    CEO --> CLI[nexus CLI]
    CEO --> TUI[Terminal TUI]

    GUI --> ProductStatus[nexus status<br/>product status]
    GUI --> OrgDashboard[Organization Dashboard]
    CLI --> ProductCLI[Product CLI]
    TUI --> ProductCLI

    ProductCLI --> Setup[Setup + Config]
    ProductCLI --> Router[Hybrid Model Router]
    ProductCLI --> OrgDaemon[Organizational Daemon]

    Setup --> DebPackage[Debian Package .deb]
    DebPackage --> Systemd[nexus.service]
    Systemd --> OrgDaemon

    Router --> LocalAI[Local AI via Ollama<br/>qwen2.5:3b or detected model]
    Router --> CloudAI[Cloud AI via Ollama<br/>gemma4:31b-cloud]

    OrgDaemon --> Blackboard[Shared Blackboard]
    OrgDaemon --> Agents[Agent Registry]
    OrgDaemon --> Runtime[Reality Runtime Engine]
    OrgDaemon --> Safety[Safety Gate + Approval Manager]
    OrgDaemon --> Observer[Linux Observer]
    OrgDaemon --> Memory[SQLite Organizational Memory]
    OrgDaemon --> Verification[Verification Engine]

    Agents --> CEOAgent[CEO Agent<br/>priority]
    Agents --> Planner[Planner Agent<br/>tasks]
    Agents --> DevOps[DevOps Agent<br/>environment]
    Agents --> Reviewer[Reviewer Agent<br/>quality]
    Agents --> Guardian[Guardian Agent<br/>risk]
    Agents --> MemoryAgent[Memory Agent<br/>learning]
    Agents --> ObserverAgent[Observer Agent<br/>context]

    Safety --> ApprovalQueue[Human Approval Queue]
    ApprovalQueue --> Runtime
    Runtime --> Logs[stdout / stderr / exit code / duration]
    Runtime --> Evidence[Evidence files]
    Logs --> Verification
    Evidence --> Verification

    Verification --> Memory
    Blackboard --> Memory
    Observer --> Memory
    OrgDaemon --> Incidents[Incident Center]

    GUI --> PublicMode[Public Mode<br/>clear operational view]
    GUI --> EngineeringMode[Engineering Mode<br/>logs, ids, traces]

    ProductStatus --> GUI
    Incidents --> GUI
    Memory --> GUI
    Verification --> GUI
```

## Reading the system by role

CEO:

- reads mission, risk, approval queue and incident impact;
- does not need raw logs or internal IDs;
- can decide whether the operation should continue.

CTO:

- reads architecture, routing, daemon health, agent ownership and verification;
- uses Engineering Mode when technical evidence is needed;
- validates systemd, packaging, runtime and rollback details.

Beginner user:

- sees what NEXUS is doing, who is acting and whether it succeeded;
- sees local AI versus cloud AI without needing implementation details;
- approves only when the consequence is understandable.

## UI sections

- Overview: executive summary of platform, mission, swarm and health.
- Missions: objective, progress and next steps.
- Swarm: agents, responsibilities and handoff flow.
- Executions: real actions, result, verification and next step.
- Approvals: sensitive actions waiting for human decision.
- Incidents: summarized failures, severity and impact.
- Observer: current Linux context.
- Telemetry: four essential cognitive signals.
- Memory: decisions, events and organizational learning.
- Config: .deb install, daemon, local model, gemma4 cloud model and display mode.
