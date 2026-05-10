# Contributing to NEXUS by ZEUS Protocol

First off, thank you for considering contributing to NEXUS! It's people like you that make this cognitive OS layer a reality.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/zeusinfra/ZEUS_NEXUS.git
   cd ZEUS_NEXUS
   ```

2. **Python Environment (Backend & AI):**
   We recommend using a virtual environment.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-base.txt
   ```

3. **Rust Environment (Systems & Sensors):**
   Ensure you have Rust installed via `rustup`.
   ```bash
   cargo build --manifest-path core-rust/Cargo.toml
   ```

## Workflow

1. Fork the repository and create your branch from `main`.
2. Name your branch descriptively: `feature/my-feature` or `bugfix/issue-description`.
3. If you've added code that should be tested, add tests to the `tests/` directory.
4. Ensure the test suite passes locally (`pytest tests/`).
5. Ensure your Rust code is properly formatted (`cargo fmt`) and passes linting (`cargo clippy`).

## Submitting a Pull Request

- Open a PR against the `main` branch.
- Fill out the provided Pull Request Template.
- Link any relevant issues.
- Be prepared to discuss your code and make changes if requested by maintainers.

## Security Changes

If you are proposing a change to `RootDaemon`, `SudoBroker`, or any system-level policy enforcement, please highlight this in your PR. Security-sensitive patches require thorough review and testing against local isolation rules.
