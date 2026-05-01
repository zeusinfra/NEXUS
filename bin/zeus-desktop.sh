#!/bin/bash
# ══════════════════════════════════════
#  ZEUS — Desktop Bubble Launcher
# ══════════════════════════════════════
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$DIR")"

echo "🧠 Iniciando ZEUS Cognitive Bubble (Overlay)..."

# 1. Start backend if not running
pkill -f "watcher_rs" || true
pkill -f "memory_service" || true

if ! pgrep -f "apps.web_gui" > /dev/null; then
    echo "🌑 Iniciando backend do ZEUS em modo headless..."
    "$DIR/zeus" server &
    sleep 3
else
    echo "✅ Backend do ZEUS já está rodando."
fi

# 2. Build or launch Flutter extension
EXT_DIR="$ROOT_DIR/zeus_extension"
LINUX_BIN="$EXT_DIR/build/linux/x64/release/bundle/zeus_extension"

if [ ! -f "$LINUX_BIN" ]; then
    echo "🏗️ Compilando a extensão Flutter pela primeira vez..."
    cd "$EXT_DIR" && flutter build linux
fi

# 3. Autostart setup prompt (optional)
AUTOSTART_FILE="$HOME/.config/autostart/zeus-bubble.desktop"
if [ ! -f "$AUTOSTART_FILE" ]; then
    mkdir -p "$HOME/.config/autostart"
    cat <<EOF > "$AUTOSTART_FILE"
[Desktop Entry]
Type=Application
Exec=$DIR/zeus-desktop.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=ZEUS Bubble
Comment=ZEUS Cognitive Overlay
EOF
    echo "⚙️  Configurado para inicializar com o sistema (Autostart)."
fi

echo "🚀 Abrindo a Bolha..."
# 4. Launch the binary
cd "$EXT_DIR" && "$LINUX_BIN" &
