#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

export ZEUS_TESTING=1
export ZEUS_SKIP_DOTENV=1

"$PYTHON_BIN" -m ruff check zeus_core apps communication tests
"$PYTHON_BIN" -m flake8 zeus_core apps communication tests --count --select=E9,F63,F7,F82 --show-source --statistics
"$PYTHON_BIN" -m pytest

for crate in core-rust watcher_rs; do
  if [ -f "$crate/Cargo.toml" ]; then
    (cd "$crate" && cargo fmt --all -- --check && cargo clippy --all-targets -- -D warnings && cargo test --all-targets)
  fi
done
