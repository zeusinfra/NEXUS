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
