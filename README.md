# ZEUS Cognitive AI

ZEUS is a local-first cognitive operating layer that combines a FastAPI backend, Ollama/OpenAI-compatible LLM routing, realtime HUD telemetry, voice/vision tools, Rust-based file watching, a Linux Mint/Cinnamon panel applet, and an event-driven **Second Brain Orchestrator** connecting Obsidian, Notion, and Linear.

The current default profile is **Ollama Cloud through the local Ollama daemon**, using `gemma4:31b-cloud` when the machine is authenticated with `ollama signin`.

Current product direction: **the Cinnamon applet is the primary desktop interface**. The desktop chat is GTK and is launched from the Cinnamon applet.

## Current Status

- Backend: FastAPI + Socket.IO + native WebSocket.
- LLM: Ollama-first, with OpenAI/Gemini support available by environment variables.
- Second Brain: Event-driven orchestration syncing local Obsidian notes to Notion and Linear via markdown tags (`#to-notion`, `#to-linear`).
- UI: Web HUD in `public/index.html`, Cinnamon applet in `applets/cinnamon/zeus@local/`, and GTK chat in `bin/zeus-gtk-chat`.
- Security: LAN access requires token when enabled; command execution uses allowlist, confirmation, and audit logging.
- Observability: structured JSON logs, request correlation-id, and health metrics.
- Tests: Python unit/contract tests plus Node tests for frontend behavior.

## Architecture

```mermaid
graph TD
    User[User] --> WebHUD[Web HUD]
    User --> Applet[Cinnamon Applet]
    User --> Obsidian[Obsidian Vault]

    WebHUD --> API[FastAPI Backend]
    Applet --> API
    Obsidian --> Watcher[File Watcher]

    Watcher --> API
    API --> LLM[LLM Provider]
    API --> Memory[SQLite / Vector Memory]
    API --> EventBus[Event Bus & Classifier]
    
    EventBus --> Notion[Notion API]
    EventBus --> Linear[Linear API]

    LLM --> Ollama[Ollama Local / Cloud]
    LLM --> OpenAI[OpenAI-compatible API]
```

## Main Directories

| Path | Purpose |
| --- | --- |
| `apps/` | FastAPI app, realtime hub, status routes, orchestration entrypoints. |
| `zeus_core/` | LLM routing, agents, memory, security guards, event bus, integrations (Notion, Linear), observability. |
| `public/` | Web HUD and frontend tests. |
| `applets/` | Linux desktop panel integrations, currently Cinnamon `zeus@local`. |
| `bin/zeus-gtk-chat` | Lightweight GTK desktop chat launched by the applet. |
| `watcher_rs/` | Rust filesystem watcher. |
| `core-rust/` | Rust memory/system components. |
| `docs/` | Technical reports and execution plans. |
| `tests/` | Python regression, security, policy, route, and observability tests. |

## Environment

Use `.env.example` as the template for local configuration. Do not commit `.env`.

Recommended local/cloud Ollama profile:

```env
ZEUS_ENV=local
ZEUS_LLM_PROVIDER=ollama
ZEUS_LLM_URL=http://127.0.0.1:11434/api/chat
ZEUS_LLM_MODEL=gemma4:31b-cloud
ZEUS_PREFER_OLLAMA=1
ZEUS_DISABLE_OLLAMA=0
ZEUS_ALLOW_LAN=0
ZEUS_LAN_AUTH=1
ZEUS_ALLOW_INSECURE_DEV_SECRET=0

# Second Brain Integrations
ZEUS_VAULT_PATH=/home/zeus/Documentos/Brain
ZEUS_DB_PATH=./zeus_events.db
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_database_id
LINEAR_API_KEY=your_linear_key
LINEAR_TEAM_ID=your_team_id
ZEUS_ENABLE_SECOND_BRAIN=1
ZEUS_ENABLE_NOTION=true
ZEUS_ENABLE_LINEAR=true
```

For Ollama Cloud via the local daemon:

```bash
ollama signin
```

For hosted Ollama API usage, configure one of:

```env
OLLAMA_API_KEY=your_ollama_api_key_here
ZEUS_LLM_API_KEY=your_ollama_api_key_here
```

For OpenAI-compatible usage:

```env
ZEUS_LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

## Run

Backend/headless:

```bash
source .venv/bin/activate
python -m apps.web_gui --headless
```

Backend health guard:

```bash
./bin/zeus ensure-server
```

Linux Mint/Cinnamon applet:

```bash
chmod +x bin/install-cinnamon-applet.sh
./bin/install-cinnamon-applet.sh
cinnamon-settings applets
```

Then enable **ZEUS Cognitive AI** in Cinnamon Applets. The applet talks to the local backend through:

```text
GET  http://127.0.0.1:8080/api/applet/status
POST http://127.0.0.1:8080/api/applet/chat
POST http://127.0.0.1:8080/api/applet/voice/start
POST http://127.0.0.1:8080/api/applet/vision/analyze
```

The applet shows backend/LLM status in the Cinnamon panel. Click behavior:

- backend online: opens the external GTK chat window from `bin/zeus-gtk-chat`;
- backend offline: runs `./bin/zeus ensure-server`.

GTK chat dependency on Debian/Ubuntu/Linux Mint:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0
```

The applet intentionally avoids Cinnamon popup widgets because some Cinnamon/GJS versions reject popup menu parameters and unload the applet. If Cinnamon does not reload the applet after installation, run:

```bash
gdbus call --session --dest org.Cinnamon --object-path /org/Cinnamon --method org.Cinnamon.ReloadXlet zeus@local APPLET
```

Web HUD:

```text
http://127.0.0.1:8080
```

## Test

Python:

```bash
python3 -m unittest discover tests
```

Frontend:

```bash
node --test public/tests/*.test.js
```

Rust:

```bash
cargo test --manifest-path core-rust/Cargo.toml
cargo test --manifest-path watcher_rs/Cargo.toml
```

## Security And Repository Hygiene

The repository must not include local secrets, runtime memory, logs, screenshots, private keys, or temporary scratch data.

Ignored/local-only examples:

- `.env`
- `.env.*`
- `configs/*.pem`
- `configs/serviceAccountKey.json`
- `data/`
- `logs/`
- `scratch/`
- `*.db`
- `*.sqlite`
- `*.log`
- `startup_test*.log`

Runtime hardening currently enforced by the backend:

- `/api/status`, `/api/health`, `/api/chat`, `/api/web-context`, applet routes, ASR, and vision endpoints require trusted local/LAN access.
- LAN mode should set `ZEUS_ALLOW_LAN=1`, `ZEUS_LAN_AUTH=1`, and a strong `ZEUS_LAN_TOKEN`.
- `ZEUS_MAX_CHAT_MESSAGE_CHARS`, `ZEUS_MAX_WEB_CONTEXT_CHARS`, and `ZEUS_MAX_VISION_IMAGE_BYTES` cap user-provided payload sizes.
- Command execution uses `ZEUS_CMD_ALLOWLIST`; interpreter execution flags such as `python3 -c`, `python3 -m`, and `node -e` require explicit confirmation.

Before pushing to a public remote, run:

```bash
git status --short
git ls-files | rg "^(configs/.*\\.pem|logs/|.*\\.log$|startup_test|scratch/|data/|.*\\.db$|.*\\.sqlite$|\\.env$|\\.env\\.)"
rg -l "(sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,}|mongodb\\+srv://|postgresql://|hvs\\.|private_key|serviceAccountKey)" --glob '!data/**' --glob '!logs/**' --glob '!scratch/**'
```

Expected result: no tracked secrets. `.env.example` may appear in pattern scans because it intentionally contains placeholder variable names.

## Git Remote

Current GitHub remote:

```text
https://github.com/geniusdev-tech/zeus-cognitive-os.git
```

To push after review:

```bash
git push origin main
```

## Documentation

- `docs/ZEUS_SECOND_BRAIN_ARCHITECTURE.md`
- `docs/RELATORIO_SISTEMA_2026-05-02.md`
- `docs/PLANO_EXECUCAO_ZEUS_2026-05-02.md`
- `docs/ANALISE_SISTEMA_DETALHADA.md`
