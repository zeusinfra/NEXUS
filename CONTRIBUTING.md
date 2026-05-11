# Contributing to NEXUS

Thanks for helping improve NEXUS. This project sits close to the operating
system, so good contributions are clear, tested, and careful with local data,
credentials, and privileged actions.

## Before You Start

- Read [README.md](README.md) for the architecture and setup.
- Read [SECURITY.md](SECURITY.md) before touching auth, RootDaemon, command
  policy, network access, filesystems, secrets, or integrations.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep real secrets out of commits. Use `.env` locally and update
  `.env.example` only with safe placeholders.

## Development Setup

```bash
git clone https://github.com/nexusinfra/NEXUS.git
cd NEXUS

./scripts/bootstrap.sh
source .venv/bin/activate
cp .env.example .env
```

Install system dependencies when needed:

```bash
sudo apt update
sudo apt install -y python3-dev libudev-dev build-essential
```

Build Rust workspaces:

```bash
cargo build --manifest-path core-rust/Cargo.toml
cargo build --manifest-path watcher_rs/Cargo.toml
```

## Workflow

1. Create a branch from `main`.
2. Use a descriptive branch name, such as `fix/root-daemon-audit-path` or
   `feat/second-brain-sync`.
3. Keep changes focused. Avoid unrelated refactors in the same pull request.
4. Add or update tests for behavior changes.
5. Update docs when behavior, setup, configuration, or security posture
   changes.
6. Run the relevant local checks before opening a pull request.

## Local Checks

Python:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Rust:

```bash
cd core-rust
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets

cd ../watcher_rs
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
```

Convenience targets:

```bash
make lint
make test
make rust
make ci
```

## Pull Requests

Open pull requests against `main`.

Include:

- What changed.
- Why it changed.
- How it was tested.
- Any configuration or migration notes.
- Screenshots or terminal output for UI and operator-surface changes.
- Security impact, if any.

Do not include:

- Real API keys, tokens, private keys, cookies, database dumps, personal vaults,
  or production logs.
- Generated caches or large local artifacts.
- Broad formatting churn outside the change area.

## Security-Sensitive Changes

Call out security-sensitive changes clearly in the pull request title or body.
This includes changes to:

- RootDaemon and privileged execution.
- Command classification, allowlists, blocklists, and approval flows.
- Authentication, tokens, secrets, CORS, host checks, or LAN exposure.
- File path validation, backup/restore, vault sync, or external integrations.
- CI security scanning, CodeQL, Gitleaks, Trivy, or Dependabot policy.

Security-sensitive changes should include tests for both allowed and rejected
paths where practical.

## Coding Guidelines

- Prefer existing project patterns over new abstractions.
- Keep runtime defaults local-first and conservative.
- Use structured parsing and APIs instead of ad hoc string manipulation when
  possible.
- Keep test fixtures isolated from developer runtime state.
- Avoid `shell=True` for new execution paths unless there is a documented
  policy reason and review coverage.
- Add comments only where they clarify non-obvious behavior.

## Documentation

Update documentation when you change:

- Setup steps or dependencies.
- Launcher commands.
- Environment variables.
- Security behavior.
- Integration behavior.
- Test or CI expectations.

Small docs improvements are welcome even when they are not tied to code
changes.
