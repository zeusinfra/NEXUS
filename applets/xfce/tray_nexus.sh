#!/usr/bin/env bash

# Configurações de Caminho
NEXUS_DIR="$HOME/Documentos/NEXUS/NEXUS"
ICON="/usr/share/icons/Papirus/32x32/apps/brain.svg"

# Função para verificar status e retornar ícone/tooltip
get_status() {
    if curl -s --max-time 1 http://127.0.0.1:8080/api/health > /dev/null; then
        echo "icon:$ICON"
        echo "tooltip:NEXUS: Operacional"
    else
        echo "icon:process-stop"
        echo "tooltip:NEXUS: Offline"
    fi
}

# Exporta funções para serem chamadas pelo YAD
export -f get_status

# Cria o pipe para comunicação com o YAD
PIPE=$(mktemp -u --tmpdir nexus_tray.XXXXXX)
mkfifo "$PIPE"

# Comando para fechar o pipe ao sair
trap "rm -f $PIPE" EXIT

# Inicia o YAD em modo notificação (Tray Icon)
yad --notification \
    --listen \
    --image="$ICON" \
    --text="NEXUS Cognitive Layer" \
    --command="$NEXUS_DIR/bin/nexus chat" \
    < "$PIPE" &

# Menu de contexto (Botão Direito)
# Formato: Rótulo!Comando!Ícone
MENU="Abrir Chat!$NEXUS_DIR/bin/nexus chat!chat\n"
MENU+="Cyber TUI!xfce4-terminal -e '$NEXUS_DIR/bin/nexus tui'!utilities-terminal\n"
MENU+="Ver Logs!xfce4-terminal -e '$NEXUS_DIR/bin/nexus logs'!text-x-generic\n"
MENU+="--separator--\n"
MENU+="Reiniciar Backend!$NEXUS_DIR/bin/nexus ensure-server!view-refresh\n"
MENU+="--separator--\n"
MENU+="Sair do Applet!quit!application-exit"

# Loop de atualização de status (a cada 10 segundos)
while true; do
    # Atualiza Ícone e Tooltip
    if curl -s --max-time 1 http://127.0.0.1:8080/api/health > /dev/null; then
        echo "icon:$ICON" > "$PIPE"
        echo "tooltip:NEXUS: Operacional" > "$PIPE"
    else
        echo "icon:process-stop" > "$PIPE"
        echo "tooltip:NEXUS: Offline (Clique para tentar iniciar)" > "$PIPE"
    fi
    
    # Atualiza o Menu
    echo "menu:$MENU" > "$PIPE"
    
    sleep 10
done
