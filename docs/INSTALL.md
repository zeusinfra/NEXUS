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
cd nexus-iced
cargo run
```

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
- `/etc/nexus/config.toml`
- `/etc/nexus/nexus.env`
- `/var/lib/nexus/`
- `/var/log/nexus/`
- `/lib/systemd/system/nexus.service`

Secrets belong in `/etc/nexus/nexus.env`, not in source code.

Architecture overview: [FLOWCHART.md](FLOWCHART.md).
