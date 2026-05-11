# NEXUS by ZEUS Protocol

> Local-first cognitive operations for Linux desktops.

NEXUS is an autonomous cognitive operating layer that helps a Linux operator
observe, reason about, and act on a local workstation. It combines a FastAPI
backend, GTK and terminal interfaces, SQLite memory, Rust system components,
voice/vision hooks, peripheral monitoring, and a guarded privileged-action
path through RootDaemon.

The project is designed around a simple principle: local context and system
control should stay local by default, and risky actions should be explicit,
auditable, and reversible.

## What NEXUS Does

- Provides a desktop operator console through GTK4 and a Cyber TUI fallback.
- Runs a local backend for chat, telemetry, cognition, events, and health.
- Routes LLM work through configurable local or hosted providers.
- Persists conversation, cognitive, and operational state in SQLite-backed
  stores.
- Watches USB, Bluetooth, filesystem, and runtime signals for useful context.
- Integrates with Second Brain workflows across Obsidian, Notion, and Linear.
- Gates privileged commands through policy checks, approval records, audit
  logs, and RootDaemon isolation.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `apps/` | FastAPI app, routes, web GUI, cognitive entrypoints |
| `zeus_core/` | Core orchestration, security, cognition, memory, integrations |
| `bin/` | Launchers for backend, GTK chat, TUI, and local helpers |
| `core-rust/` | Rust workspace for memory, sensors, policy, state, and bridges |
| `watcher_rs/` | Rust watcher service |
| `applets/` | Cinnamon desktop applet |
| `requirements/` | Python dependency profiles |
| `tests/` | Unit, integration, and system tests |
| `.github/workflows/` | CI for Python, Rust, CodeQL, and security scanning |

## Requirements

NEXUS targets Debian, Ubuntu, and Linux Mint style systems.

- Python 3.10 or 3.12
- Rust stable with `cargo`
- `python3-venv`, `python3-dev`, `build-essential`
- `libudev-dev` for device monitoring tests and integrations
- GTK4/Libadwaita packages for the desktop chat
- Optional: Ollama for local model routing

Example system packages:

```bash
sudo apt update
sudo apt install -y \
  python3-venv python3-dev build-essential libudev-dev \
  python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0
```

## Quick Start

```bash
git clone https://github.com/zeusinfra/NEXUS.git
cd NEXUS

./scripts/bootstrap.sh
source .venv/bin/activate

cp .env.example .env
```

Run the default terminal operator surface:

```bash
./bin/zeus
```

Run specific surfaces:

```bash
./bin/zeus tui
./bin/zeus chat
./bin/zeus server
./bin/zeus ensure-server
```

Build the Rust workspaces:

```bash
cargo build --manifest-path core-rust/Cargo.toml
cargo build --manifest-path watcher_rs/Cargo.toml
```

## Common Commands

| Command | Description |
| --- | --- |
| `pip install -r requirements/base.txt` | Install base dependencies |
| `pip install -r requirements/dev.txt` | Install development dependencies |
| `make bootstrap` | Create `.venv` and install development dependencies |
| `make lint` | Run Python lint checks |
| `make test` | Run the Python test suite |
| `make rust` | Run Rust format, clippy, and tests |
| `make ci` | Run the main local CI gate |
| `./bin/zeus help` | Show launcher commands |
| `./bin/install-cinnamon-applet.sh` | Install the Cinnamon applet locally |

## Configuration

Copy `.env.example` to `.env` and enable only the integrations you need.

Important settings:

- `ZEUS_LLM_PROVIDER`: `ollama`, `openai`, `gemini`, or local defaults
- `ZEUS_LLM_URL`: hosted or local LLM endpoint
- `ZEUS_DB_PATH`: SQLite event and cognition database path
- `ZEUS_VAULT_PATH`: local knowledge vault path
- `ZEUS_AUTONOMY_LEVEL`: guarded execution mode
- `ZEUS_ENABLE_SECOND_BRAIN`: enable Second Brain workers
- `ZEUS_ENABLE_VOICE_SENSING`: enable voice sensing
- `ZEUS_ENABLE_BROWSER_SENSING`: enable browser sensing

Secrets belong in local environment files or secret managers. Do not commit
real API keys, tokens, private keys, database dumps, or personal vault content.

## Architecture

```mermaid
flowchart TD
    Operator[Operator] --> GTK[GTK4 Chat]
    Operator --> TUI[Cyber TUI]
    Operator --> Applet[Cinnamon Applet]

    GTK --> API[FastAPI Backend]
    TUI --> API
    Applet --> API

    API --> LLM[LLM Router]
    API --> Memory[SQLite Memory]
    API --> Events[Event Bus]
    API --> Cognition[Cognitive Loop]
    API --> Security[RootDaemon + Policy]
    API --> Peripherals[USB + Bluetooth]
    API --> Watcher[Rust Watcher]

    Events --> Obsidian[Obsidian Vault]
    Events --> Notion[Notion]
    Events --> Linear[Linear]
    LLM --> Local[Local Models]
    LLM --> Hosted[Hosted Providers]
```

## Security Model

NEXUS assumes local-first operation and treats system-level execution as a
security boundary.

- RootDaemon communicates over a restricted Unix socket.
- Privileged actions are classified before execution.
- Dangerous command patterns are blocked by policy.
- Higher-risk actions require explicit approval context.
- Audit logs record command, caller, risk, reason, and outcome.
- Tests isolate runtime paths to avoid touching developer state.

Read [SECURITY.md](SECURITY.md) before changing command policy, RootDaemon,
authentication, token handling, network exposure, or filesystem boundaries.

## Testing

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
cd core-rust && cargo test --all-targets
cd ../watcher_rs && cargo test --all-targets
```

CI currently covers Python 3.10 and 3.12, Rust checks, CodeQL analysis, secret
scanning, and Trivy filesystem scanning.

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), and
follow the [Code of Conduct](CODE_OF_CONDUCT.md).

Security-sensitive reports should not be opened as public issues. Use the
process in [SECURITY.md](SECURITY.md).

## License

NEXUS is released under the [MIT License](LICENSE).
