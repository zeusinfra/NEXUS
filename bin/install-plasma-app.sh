#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$APP_DIR/nexus-plasma-chat.desktop"

mkdir -p "$APP_DIR"
install -m 0644 "$ROOT_DIR/applets/plasma/nexus-plasma-chat.desktop" "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo "NEXUS Plasma instalado em: $DESKTOP_FILE"
