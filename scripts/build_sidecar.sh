#!/bin/bash
# ══════════════════════════════════════════════════════
#  NEXUS Sidecar Builder
#  Transforma o Backend Python em um binário para o Tauri
# ══════════════════════════════════════════════════════

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$DIR")"
BINARY_NAME="nexus-backend"
TARGET_DIR="$ROOT_DIR/src-tauri/binaries"

mkdir -p "$TARGET_DIR"

echo "📦 Instalando dependências de build..."
pip install pyinstaller

echo "🚀 Compilando Backend Python com PyInstaller..."
# Adicionamos --collect-all para garantir que o FastAPI e dependências sejam incluídos
pyinstaller --noconfirm --onefile --console \
    --name "$BINARY_NAME" \
    --collect-all fastapi \
    --collect-all uvicorn \
    --collect-all nexus_core \
    --add-data "$ROOT_DIR/public:public" \
    "$ROOT_DIR/apps/web_gui.py"

# Identifica a arquitetura para o nome do binário do Tauri (ex: nexus-backend-x86_64-unknown-linux-gnu)
ARCH=$(rustc -Vv | grep host | cut -d ' ' -f 2)
mv "dist/$BINARY_NAME" "$TARGET_DIR/$BINARY_NAME-$ARCH"

echo "✅ Sidecar compilado com sucesso em: $TARGET_DIR/$BINARY_NAME-$ARCH"
