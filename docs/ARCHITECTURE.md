# NEXUS architecture

NEXUS is organized as a supervised cognitive runtime for Linux.

See the complete Mermaid diagram in [FLOWCHART.md](FLOWCHART.md).

Core flow:

```text
User
-> CLI/TUI/API
-> Cognitive Orchestrator
-> Model Router
-> Agents
-> Safety Gate
-> Runtime Executor
-> Audit Logs
-> Verified Response
```

Hybrid model routing:

- `simple`: local Ollama
- `normal`: local Ollama
- `complex`: cloud model `gemma4:31b-cloud`
- `critical`: cloud model `gemma4:31b-cloud` plus reviewer and human approval

Local Ollama is the reflexive path for summarization, classification, log
inspection and quick offline tasks. The strategic cloud path uses
`gemma4:31b-cloud`, exposed through the Ollama provider configuration, for
architecture, security review, risky commands and package/systemd decisions.

Main modules:

- `nexus_core/model_router.py`: complexity/risk routing decision.
- `nexus_core/models/ollama_client.py`: Ollama detection, model listing and
  generation through the local API.
- `nexus_core/models/model_registry.py`: combined cloud/local status.
- `nexus_core/product_cli.py`: Linux product CLI surface.
- `nexus_core/organization/*`: existing daemon, memory, runtime, verification
  and security layers.

## Interface model

The Rust/Iced frontend is organized like an understandable company operating
system:

- CEO view: mission, impact, approvals and incidents.
- CTO view: architecture, agents, runtime health and verification.
- Beginner view: what is happening, who is acting and whether it succeeded.

The GUI defaults to Public Mode for clarity and exposes Engineering Mode for
logs, internal IDs, stdout/stderr and deeper runtime diagnostics.
