# ZEUS Second Brain Architecture

## Visão Geral
Esta arquitetura transforma o ZEUS de um simples assistente reativo para um "Segundo Cérebro" orquestrador, seguindo o pipeline:
1. **Pensar:** Obsidian (Arquivos Markdown locais)
2. **Orquestrar:** ZEUS (Event Bus via SQLite)
3. **Organizar:** Notion (Documentação em nuvem estruturada)
4. **Executar:** Linear (Issues, Bugs, Roadmap técnico)

## Fluxo Orientado a Eventos
1. O `watcher.py` (via `os.stat`) detecta novas notas ou alterações no `ZEUS_VAULT_PATH`.
2. O `event_bus.py` aplica *debounce*, calcula o SHA-256 e, se houver mudança real, salva no banco `zeus_events.db`.
3. O `sync_worker.py` lê os eventos pendentes assincronamente e os delega ao `classifier.py`.
4. O classificador lê as tags da nota (`#to-notion`, `#to-linear`, `#bug`) e engatilha as integrações `notion.py` e `linear.py`.

## Variáveis de Ambiente
As seguintes variáveis devem ser preenchidas no seu `.env` para habilitar o fluxo completo:
```ini
ZEUS_VAULT_PATH=/home/zeus/Documentos/Brain
ZEUS_DB_PATH=./zeus_events.db
ZEUS_ENABLE_SECOND_BRAIN=1

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
