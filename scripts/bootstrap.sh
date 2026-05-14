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
"$VENV_DIR/bin/python" -m pip install pyinstaller

echo "🛠️ Preparando ambiente de build Rust..."
if ! command -v cargo &> /dev/null; then
    echo "⚠️ Rust/Cargo não encontrado. Instale via https://rustup.rs para compilar o shell."
else
    # Garante que o target do Tauri esteja pronto
    rustup target add $(rustc -Vv | grep host | cut -d ' ' -f 2) 2>/dev/null || true
fi

echo "✅ Bootstrap complete. Activate with: source $VENV_DIR/bin/activate"
