#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements/dev.txt
  # Garante que o core Rust seja compilado
  cargo build --manifest-path core-rust/Cargo.toml --release
  cargo build --manifest-path nexus-iced/Cargo.toml --release

echo "✅ Bootstrap complete. Activate with: source $VENV_DIR/bin/activate"
