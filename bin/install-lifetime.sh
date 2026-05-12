#!/bin/bash
# NEXUS Lifetime Installation Script

echo "🧠 Iniciando instalação vitalícia do NEXUS..."

# 1. Garantir que o diretório de logs existe
mkdir -p /home/zeus/Documentos/ZEUS_SYSTEM/logs

# 2. Criar diretório do systemd de usuário se não existir
mkdir -p ~/.config/systemd/user/

# 3. Copiar os arquivos de serviço
cp deploy/systemd/nexus.service ~/.config/systemd/user/nexus.service
cp deploy/systemd/nexus-root-daemon.service ~/.config/systemd/user/nexus-root-daemon.service

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

# 6. Adicionar ao Autostart do Cinnamon (Opcional, pois o Applet já faz isso)
# O Applet do Cinnamon já inicia automaticamente com o painel.

echo "🚀 NEXUS está agora em estado VITALÍCIO."
