#!/bin/bash
# NEXUS Lifetime Installation Script
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🧠 Iniciando instalação vitalícia do NEXUS..."

# 1. Garantir que o diretório de logs existe
mkdir -p "$ROOT_DIR/logs"

# 2. Criar diretório do systemd de usuário se não existir
mkdir -p ~/.config/systemd/user/
mkdir -p ~/.config/autostart/

# 3. Copiar e ajustar os arquivos de serviço
sed -e "s|WorkingDirectory=.*|WorkingDirectory=$ROOT_DIR|" \
    -e "s|ExecStart=.*|ExecStart=$ROOT_DIR/.venv/bin/python -m apps.web_gui|" \
    -e "s|StandardOutput=append:.*|StandardOutput=append:$ROOT_DIR/logs/systemd_out.log|" \
    -e "s|StandardError=append:.*|StandardError=append:$ROOT_DIR/logs/systemd_err.log|" \
    deploy/systemd/nexus.service > ~/.config/systemd/user/nexus.service

sed -e "s|WorkingDirectory=.*|WorkingDirectory=$ROOT_DIR|" \
    -e "s|ExecStart=.*|ExecStart=$ROOT_DIR/.venv/bin/python -m nexus_core.security.root_daemon|" \
    -e "s|StandardOutput=append:.*|StandardOutput=append:$ROOT_DIR/logs/root_daemon.log|" \
    -e "s|StandardError=append:.*|StandardError=append:$ROOT_DIR/logs/root_daemon.log|" \
    deploy/systemd/nexus-root-daemon.service > ~/.config/systemd/user/nexus-root-daemon.service

# 4. Recarregar o daemon do systemd
systemctl --user daemon-reload

# 5. Desativar serviços antigos do ZEUS (se existirem)
systemctl --user stop zeus.service zeus-root-daemon.service 2>/dev/null || true
systemctl --user disable zeus.service zeus-root-daemon.service 2>/dev/null || true

# 6. Habilitar e iniciar os serviços NEXUS
systemctl --user enable nexus.service nexus-root-daemon.service
systemctl --user restart nexus.service nexus-root-daemon.service

echo "✅ Backend NEXUS configurado como serviço de usuário."
echo "🔄 O sistema irá reiniciar automaticamente em caso de falha."
echo "📡 Use 'systemctl --user status nexus.service' para monitorar."

# 7. Restaurar abertura automática do chat no login
rm -f ~/.config/autostart/zeus-chat-autostart.desktop
cat > ~/.config/autostart/nexus-chat-autostart.desktop <<EOF
[Desktop Entry]
Type=Application
Name=NEXUS Unified GUI
Comment=Abre a interface unificada NEXUS (Rust Iced) ao iniciar a sessao
Exec=$ROOT_DIR/bin/nexus
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "🪟 Interface NEXUS configurada para abrir no login."

echo "🚀 NEXUS está agora em estado VITALÍCIO."
