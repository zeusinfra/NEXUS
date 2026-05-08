# ZEUS Second Brain Architecture

## Visão Geral
Esta arquitetura transforma o ZEUS de um assistente reativo em um "Segundo Cérebro" bi-direcional:
1. **Percepção:** Filesystem Mirror (Reflete a estrutura do SO no Obsidian).
2. **Pensar:** Obsidian (Arquivos Markdown locais como interface de pensamento).
3. **Orquestrar:** ZEUS (Sync Engine e Event Pipeline via SQLite).
4. **Organizar:** Notion (Documentação estruturada e Dashboards operacionais).
5. **Executar:** Linear (Issues técnicas e Roadmap de engenharia).
6. **Observar:** Cyber-Premium Dashboard (GTK4/Web HUD com telemetria em tempo real).

## Observabilidade e Telemetria
O ecossistema agora inclui uma camada de **Observabilidade Ativa** atrelada à Governança (v4):
- **Sidebar de Telemetria:** Integrada nativamente no Chat GTK4 com LevelBars e live polling, fornece insights sobre o estado do hardware e o foco cognitivo atual.
- **Governança de Recursos:** `ResourceGovernor` adapta os ciclos de leitura do Second Brain ativamente caso a memória (RAM) ou CPU excedam limites pré-determinados.
- **Thought Bar:** Uma interface de "consciência exposta" que mostra as etapas lógicas que o ZEUS está percorrendo durante a orquestração de tarefas complexas, agora pulsando em tempo real.
- **Synaptic Log:** Visibilidade total dos eventos de sincronização entre as pontas do Second Brain diretamente no Web HUD e EventBus.

## Fluxo Orientado a Eventos
1. O **Watcher Rust** (`watcher_rs`) monitora alterações no sistema e no `ZEUS_VAULT_PATH`.
2. O **Sync Engine** (`sync_engine.py`) orquestra trabalhadores independentes:
   - **Synaptic → Obsidian:** Exporta o mapa neural e logs diários para o vault.
   - **Long-Term → Notion:** Sincroniza o perfil cognitivo e estado operacional.
   - **Insights → Linear:** Transforma anomalias e tags em issues técnicas.
3. O **Sync Worker** (`sync_worker.py`) processa a fila de eventos do `zeus_events.db` para roteamento inteligente.

## Variáveis de Ambiente
As seguintes variáveis devem ser preenchidas no seu `.env` para habilitar o fluxo completo:
```ini
ZEUS_VAULT_PATH=/home/zeus/Documentos/Brain
ZEUS_DB_PATH=./zeus_events.db
ZEUS_ENABLE_SECOND_BRAIN=1
ZEUS_ENABLE_SECOND_BRAIN_SYNC_ENGINE=0
ZEUS_ENABLE_NOTION_AUTO_SYNC=1
ZEUS_ENABLE_OBSIDIAN_AUTO_SYNC=1
ZEUS_ENABLE_LINEAR_AUTO_SYNC=1

# Notion
NOTION_TOKEN=secret_xxx
NOTION_DATABASE_ID=xxx
ZEUS_ENABLE_NOTION=true

# Linear
LINEAR_API_KEY=your_linear_api_key_here
LINEAR_TEAM_ID=xxx
ZEUS_ENABLE_LINEAR=true
```

## Como usar (Tags)
Escreva no Obsidian e adicione tags:
- `#to-notion`: Envia o conteúdo da nota para estruturação no Notion.
- `#to-linear`: Cria uma Issue com o conteúdo da nota.
- `#bug`, `#performance`: Cria issues no Linear definindo a prioridade automaticamente (bug=medium, bug+security=high).

O ZEUS cria links cruzados no `sqlite_memory.py` garantindo que o rastreio da origem (`source_path`) seja preservado.

## Modo Leve
A arquitetura funciona sem carregar LLMs locais ou Bancos Vetoriais pesados. O processamento assíncrono evita loops pesados de CPU, e a tabela `processed_files` atua como cache rígido, protegendo o sistema contra chamadas redundantes de API.
