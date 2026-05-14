#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
DESKTOP_FILE="$APP_DIR/nexus-plasma-chat.desktop"

mkdir -p "$APP_DIR"
mkdir -p "$ICON_DIR"
install -m 0644 "$ROOT_DIR/applets/plasma/nexus-plasma-chat.desktop" "$DESKTOP_FILE"
install -m 0644 "$ROOT_DIR/assets/icons/nexus-plasma-chat.svg" "$ICON_DIR/nexus-plasma-chat.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "NEXUS Plasma instalado em: $DESKTOP_FILE"
echo "Icone instalado em: $ICON_DIR/nexus-plasma-chat.svg"
