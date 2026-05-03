#!/bin/bash
# ══════════════════════════════════════
#  ZEUS — Desktop Bubble Launcher
# ══════════════════════════════════════
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$DIR")"

echo "🧠 Iniciando ZEUS Cognitive Bubble (Overlay)..."

# 1. Start backend if not running
if ! curl -fsS "http://127.0.0.1:8080/api/health" > /dev/null; then
    echo "🌑 Iniciando backend do ZEUS em modo headless..."
    "$DIR/zeus" server &
    for _ in $(seq 1 20); do
        if curl -fsS "http://127.0.0.1:8080/api/health" > /dev/null; then
            break
        fi
        sleep 1
    done
else
    echo "✅ Backend do ZEUS já está rodando."
fi

# 2. Build or launch Flutter extension
EXT_DIR="$ROOT_DIR/zeus_extension"
LINUX_BIN="$EXT_DIR/build/linux/x64/release/bundle/zeus_extension"

if [ ! -f "$LINUX_BIN" ] || find "$EXT_DIR/lib" "$EXT_DIR/pubspec.yaml" -type f -newer "$LINUX_BIN" | grep -q .; then
    echo "🏗️ Compilando a extensão Flutter atualizada..."
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
mkdir -p "$ROOT_DIR/logs"
cd "$EXT_DIR" && nohup "$LINUX_BIN" > "$ROOT_DIR/logs/zeus_bubble.log" 2>&1 &
