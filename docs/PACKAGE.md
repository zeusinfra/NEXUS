# Debian package

Build:

```bash
make deb
```

Output:

```text
dist/nexus_0.1.5_amd64.deb
```

Validate package metadata:

```bash
make test-package
```

The package skeleton is under `packaging/`:

- `packaging/debian/`: control scripts and metadata.
- `packaging/systemd/nexus.service`: system-wide daemon unit.
- `packaging/scripts/build_deb.sh`: deterministic package builder.
- `packaging/desktop/nexus.desktop`: desktop entry.

Runtime directories:

- config: `/etc/nexus/config.toml`
- secrets: `/etc/nexus/nexus.env`
- state: `/var/lib/nexus/`
- logs: `/var/log/nexus/`

Runtime state includes the organizational memory database, blackboard, approval
queue, execution artifacts, structured execution plans, verification records
and replayable command evidence.

The service runs as the `nexus` user. Package configuration creates the user
when missing and owns `/var/lib/nexus` plus `/var/log/nexus` for that runtime.

Default model packaging config:

- local provider: Ollama at `http://localhost:11434`
- local model: automatic, preferring small installed models such as `qwen2.5:3b`
- cloud provider: Ollama
- cloud model: `gemma4:31b-cloud`

Architecture overview: [FLOWCHART.md](FLOWCHART.md).

The systemd daemon starts the organizational runtime with:

```bash
/usr/bin/nexus org --config /etc/nexus/config.toml run
```

Post-install inspection commands:

```bash
nexus org --config /etc/nexus/config.toml workspace-context
nexus org --config /etc/nexus/config.toml execution-plans
nexus org --config /etc/nexus/config.toml replay-command cmd_...
nexus org --config /etc/nexus/config.toml incidents
```

Uninstalling the package stops the service and preserves user data under
`/var/lib/nexus` and `/var/log/nexus`.
