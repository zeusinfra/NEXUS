# NEXUS install

NEXUS can run from the repository during development or as a Debian package on
Debian-based distributions.

## Development

```bash
./bin/nexus status
./bin/nexus health
./bin/nexus model status
./bin/nexus router explain "resumir logs do sistema"
```

Launch the Rust/Iced conversational GUI from the repository root:

```bash
./bin/nexus
```

In repository mode the launcher can fall back to `cargo run --release` for Rust
components when compiled binaries are not present. In the Debian package, the
launcher uses compiled binaries from `/usr/lib/nexus/bin`.

The canonical runtime backend for development and deployment is Python FastAPI in
`apps/web_gui.py`. The `backend/` Rust/Axum directory is an experimental lab
project for future backend migration and is not required for the standard
repository or Debian runtime.

The local LLM path uses an existing Ollama installation. NEXUS detects the
binary, checks `http://localhost:11434/api/tags`, lists already downloaded
models and never pulls a model automatically.

The cloud route defaults to the Ollama-provider model `gemma4:31b-cloud`.
Simple and normal tasks use the selected local model, while complex and
critical tasks route to `gemma4:31b-cloud`.

After installing the `.deb`, `nexus status` reports the system install under
`/etc/nexus`, `/var/lib/nexus` and `/var/log/nexus`. To inspect the repository
runtime during development, run:

```bash
NEXUS_DEV_MODE=1 ./bin/nexus status
```

If no local model exists:

```bash
ollama pull qwen2.5:3b
```

## Runtime inspection

During development, the organizational runtime can be inspected without opening
a technical dashboard:

```bash
./bin/nexus org workspace-context
./bin/nexus org execution-plans
./bin/nexus org execution-steps --command-id cmd_...
./bin/nexus org replay-command cmd_...
./bin/nexus org replay-task task_...
./bin/nexus org incidents
```

Useful execution budget environment variables:

- `NEXUS_EXEC_CONCURRENT_LIMIT`: max active command executions.
- `NEXUS_EXEC_TIMEOUT_MAX_SEC`: max timeout accepted by the runtime.
- `NEXUS_EXEC_TOKEN_BUDGET`: planning/reasoning budget for execution flows.
- `NEXUS_EXEC_CPU_SOFT_LIMIT`: CPU pressure threshold.
- `NEXUS_EXEC_RAM_SOFT_LIMIT`: RAM pressure threshold.
- `NEXUS_EXEC_BLOCK_ON_RESOURCE_PRESSURE`: block execution when CPU/RAM pressure
  is above the configured soft limit.

## Debian package

```bash
make deb
sudo apt install ./dist/nexus_0.1.5_amd64.deb
sudo nexus setup
sudo systemctl enable --now nexus
nexus status
```

The package installs:

- `/usr/bin/nexus`
- `/usr/lib/nexus/`
- `/usr/lib/nexus/bin/nexus-iced`
- `/usr/lib/nexus/bin/watcher_rs`
- `/usr/lib/nexus/bin/memory_service`
- `/etc/nexus/config.toml`
- `/etc/nexus/nexus.env`
- `/var/lib/nexus/`
- `/var/log/nexus/`
- `/lib/systemd/system/nexus.service`

Secrets belong in `/etc/nexus/nexus.env`, not in source code.

Runtime details: [RUNTIME.md](RUNTIME.md). Architecture overview:
[FLOWCHART.md](FLOWCHART.md).
