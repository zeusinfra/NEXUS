#!/usr/bin/env bash

# Configurações
NEXUS_DIR="$HOME/Documentos/NEXUS/NEXUS"
ICON_ONLINE="🌐"
ICON_OFFLINE="🌑"
PORT=8080

# Verifica se o backend responde
if curl -s http://127.0.0.1:$PORT/api/health > /dev/null; then
    STATUS="Online"
    ICON=$ICON_ONLINE
else
    STATUS="Offline"
    ICON=$ICON_OFFLINE
fi

# Saída formatada para o Genmon do XFCE
# <img> ícone
# <txt> texto no painel
# <tool> tooltip ao passar o mouse
# <click> comando ao clicar
echo "<img>/usr/share/icons/Papirus/32x32/apps/brain.svg</img>"
echo "<txt> NEXUS </txt>"
echo "<tool>NEXUS Status: $STATUS
Clique para abrir o Chat</tool>"
echo "<click>$NEXUS_DIR/bin/nexus chat</click>"
