#!/bin/bash
# Script para iniciar o NEXUS Neural Command Center
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Ativa o venv do projeto
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "ERRO: Virtual environment não encontrado em .venv/"
    echo "Execute: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "⚡ Sincronizando NEXUS Neural Command Center na porta ${NEXUS_PORT:-8080}..."
export NEXUS_BIND_HOST="0.0.0.0"
python -m apps.web_gui "$@"
