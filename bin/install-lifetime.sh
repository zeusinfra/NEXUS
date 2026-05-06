#!/bin/bash
# ZEUS Lifetime Installation Script

echo "🧠 Iniciando instalação vitalícia do ZEUS..."

# 1. Garantir que o diretório de logs existe
mkdir -p /home/zeus/Documentos/ZEUS_SYSTEM/logs

# 2. Criar diretório do systemd de usuário se não existir
mkdir -p ~/.config/systemd/user/

# 3. Copiar o arquivo de serviço
cp zeus.service ~/.config/systemd/user/zeus.service

# 4. Recarregar o daemon do systemd
systemctl --user daemon-reload

# 5. Habilitar e iniciar o serviço
systemctl --user enable zeus.service
systemctl --user restart zeus.service

echo "✅ Backend ZEUS configurado como serviço de usuário."
echo "🔄 O sistema irá reiniciar automaticamente em caso de falha."
echo "📡 Use 'systemctl --user status zeus.service' para monitorar."

# 6. Adicionar ao Autostart do Cinnamon (Opcional, pois o Applet já faz isso)
# O Applet do Cinnamon já inicia automaticamente com o painel.

echo "🚀 ZEUS está agora em estado VITALÍCIO."
