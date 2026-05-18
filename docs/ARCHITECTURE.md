# NEXUS architecture

NEXUS is organized as a supervised cognitive runtime for Linux.

See the complete Mermaid diagram in [FLOWCHART.md](FLOWCHART.md).

Core flow:

```text
User
-> Conversational GUI / CLI / TUI / API
-> Cognitive Orchestrator
-> Model Router
-> Agents
-> Safety Gate
-> Structured Execution Plan
-> Resource Governor
-> Runtime Executor
-> Verification Engine
-> Action Replay
-> Organizational Memory
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
- `nexus_core/organization/runtime.py`: evidence-first execution runtime that
  binds approvals, command IDs, resource budgets, verification and replay.
- `nexus_core/organization/execution_plans.py`: plan -> step -> execution
  structure for approved actions.
- `nexus_core/organization/replay.py`: reconstructs command/task timelines from
  persisted runtime events, plans and verification records.
- `nexus_core/organization/workspace_context.py`: detects durable project facts
  such as Rust, Iced, Axum, SQLx, WebSocket architecture and test coverage.
- `nexus_core/organization/resource_budget.py`: enforces timeout, concurrency,
  token and resource-pressure budgets.
- `nexus_core/organization/self_healing.py`: classifies failures and produces
  safe recovery steps without bypassing approval.
- `nexus_core/organization/*`: daemon, memory, verification, security, observer
  and orchestration layers.

## Reliability model

NEXUS treats every real action as a structured, replayable unit:

```text
Approval
-> Execution plan
-> Resource budget
-> Command execution
-> Evidence capture
-> Verification
-> Self-healing diagnostic when needed
-> Replay timeline
-> Persistent memory
```

The runtime must not mark work as complete without execution evidence. A failed
command becomes a diagnosed incident with recovery steps; it does not become a
silent success.

## Interface model

The Rust/Iced frontend is organized as a premium conversational assistant:

- Minimal sidebar for conversations, tasks and settings.
- Central conversation focused on the user's intent.
- Fixed bottom input with attachments, voice and send controls.
- Suggestion cards for common cognitive workflows.
- Technical evidence remains available through runtime commands and developer
  surfaces instead of overwhelming the primary chat view.

The product direction is less dashboard and more cognitive assistant: the user
should feel clarity, verification and calm control, while the runtime preserves
the audit trail underneath.
