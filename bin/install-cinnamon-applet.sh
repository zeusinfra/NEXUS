#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$DIR")"
UUID="zeus@local"
SRC_DIR="$ROOT_DIR/applets/cinnamon/$UUID"
DEST_DIR="$HOME/.local/share/cinnamon/applets/$UUID"

if ! command -v cinnamon >/dev/null 2>&1 && ! pgrep -x cinnamon >/dev/null 2>&1; then
    echo "Aviso: Cinnamon nao foi detectado. O applet e especifico para Linux Mint/Cinnamon."
fi

if [ ! -d "$SRC_DIR" ]; then
    echo "Applet fonte nao encontrado: $SRC_DIR" >&2
    exit 1
fi

mkdir -p "$(dirname "$DEST_DIR")"
rm -rf "$DEST_DIR"
cp -R "$SRC_DIR" "$DEST_DIR"

python3 - "$DEST_DIR/applet.js" "$ROOT_DIR" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
root = sys.argv[2]
content = path.read_text(encoding="utf-8")
path.write_text(content.replace("__ZEUS_PROJECT_ROOT__", root), encoding="utf-8")
PY

echo "Applet instalado em: $DEST_DIR"
echo ""
echo "Para ativar:"
echo "  1. Abra Configuracoes do Sistema > Applets"
echo "  2. Va em Gerenciar"
echo "  3. Ative 'ZEUS Cognitive AI'"
echo ""
echo "Atalho:"
echo "  cinnamon-settings applets"
