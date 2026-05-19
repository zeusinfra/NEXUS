# Runtime

NEXUS has two supported runtime shapes: repository development and Debian
package installation. The product backend today is Python FastAPI; Rust provides
the Iced GUI plus helper services.

## Processes

| Process | Command | Purpose |
| :--- | :--- | :--- |
| Product launcher | `./bin/nexus` or `/usr/bin/nexus` | Single CLI/GUI entrypoint. |
| Python backend | `python -m apps.web_gui --headless` | FastAPI API, web GUI API surface and websocket handlers. |
| Rust GUI | `nexus-iced` | Primary desktop conversational interface. |
| Rust watcher | `watcher_rs` | Filesystem/system event websocket hub. |
| Rust memory service | `memory_service` | Local vector memory HTTP service. |
| Organization daemon | `nexus org --config /etc/nexus/config.toml run` | Supervised runtime for approvals, execution plans, verification and replay. |

In the Debian package, Rust processes run from compiled binaries installed in
`/usr/lib/nexus/bin`. Runtime startup must not depend on `cargo run`.

## Ports

| Port | Default | Owner |
| :--- | :--- | :--- |
| Backend API | `8080` | `apps.web_gui` through `NEXUS_PORT`. |
| Rust watcher websocket | `8081` | `watcher_rs` through `NEXUS_WATCHER_PORT`. |
| Rust memory service | `8085` | `memory_service` through `NEXUS_MEMORY_SERVICE_URL`. |
| Ollama API | `11434` | External Ollama installation. |

## Paths

| Path | Purpose |
| :--- | :--- |
| `/usr/bin/nexus` | System command wrapper. |
| `/usr/lib/nexus` | Installed application code and compiled runtime binaries. |
| `/etc/nexus/config.toml` | System config. |
| `/etc/nexus/nexus.env` | Secrets and environment overrides. |
| `/var/lib/nexus` | State, approvals, tasks, memory and runtime data. |
| `/var/log/nexus` | System daemon logs. |

During repository development, runtime state belongs under `runtime/` and logs
under `logs/`; both are ignored by Git.

## systemd

The package installs `packaging/systemd/nexus.service` as
`/lib/systemd/system/nexus.service`.

Useful commands:

```bash
sudo systemctl enable --now nexus
sudo systemctl status nexus
journalctl -u nexus -n 120 --no-pager
sudo systemctl restart nexus
```

The unit runs as the `nexus` system user and sets:

```text
NEXUS_PROJECT_ROOT=/usr/lib/nexus
NEXUS_CONFIG_PATH=/etc/nexus/config.toml
NEXUS_RUNTIME_DIR=/var/lib/nexus
NEXUS_STATE_DIR=/var/lib/nexus/state
NEXUS_LOG_DIR=/var/log/nexus
```

## Flags

The stable base keeps sensing and autonomous side effects opt-in.

| Flag | Default | Meaning |
| :--- | :--- | :--- |
| `NEXUS_ENABLE_VOICE_SENSING` | `0` | Microphone/wake-word sensing. |
| `NEXUS_ENABLE_BROWSER_SENSING` | `0` | Browser context sensing. |
| `NEXUS_ENABLE_AUTONOMOUS_TASKS` | `0` | Background autonomous task execution. |
| `NEXUS_ENABLE_INTERNAL_WATCHER` | `0` | Python internal watcher; package prefers external Rust watcher. |
| `NEXUS_ENABLE_SECOND_BRAIN` | `0` | Obsidian/Notion/Linear status and sync features. |
| `NEXUS_ENABLE_OBSIDIAN_AUTO_SYNC` | `0` | Automatic Obsidian sync. |
| `NEXUS_ENABLE_NOTION_AUTO_SYNC` | `0` | Automatic Notion sync. |
| `NEXUS_ENABLE_LINEAR_AUTO_SYNC` | `0` | Automatic Linear sync. |

ASR requires `ffmpeg` and `faster_whisper`. OCR requires `tesseract`. These are
reported by `nexus health` and should stay optional.

## Troubleshooting

Run the product checks first:

```bash
nexus status
nexus health
```

If the backend does not start, check port `8080`, then inspect
`nexus_server.log` in the configured log directory. If the watcher or memory
service does not start, inspect `watcher.log` or `memory.log` in the same
directory.

If a package install reports missing binaries, rebuild with:

```bash
make deb
dpkg-deb --contents dist/nexus_0.1.5_amd64.deb | grep 'usr/lib/nexus/bin'
```

If development status accidentally resolves to the system package, force repo
mode:

```bash
NEXUS_DEV_MODE=1 ./bin/nexus status
```
