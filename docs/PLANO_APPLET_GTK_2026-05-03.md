# Plano Applet + GTK

Data: 2026-05-03

## Decisao

O ZEUS Cognitive OS passa a focar em uma experiencia desktop enxuta:

- applet Cinnamon nativo em GJS;
- chat GTK leve;
- backend FastAPI;
- Web HUD;
- Ollama/OpenAI/Gemini como provedores LLM.

Foram removidos do escopo ativo os clientes e artefatos legados que nao pertencem mais ao desenho applet + GTK.

## Arquitetura Alvo

```text
Cinnamon Panel Applet
        |
        v
GTK Chat ZEUS
        |
        v
FastAPI Backend
        |
        v
Ollama / OpenAI / Gemini
```

## Componentes Mantidos

- `apps/`: backend, rotas, realtime e orquestracao.
- `zeus_core/`: LLM, memoria, seguranca, observabilidade e agentes.
- `applets/cinnamon/zeus@local/`: applet do painel.
- `bin/zeus-gtk-chat`: chat GTK do applet.
- `bin/zeus`: launcher backend.
- `public/index.html`: HUD web.
- `watcher_rs/`: watcher Rust.
- `core-rust/`: servicos Rust.
- `tests/`: regressao e seguranca.

## Proximas Etapas

1. Fortalecer `bin/zeus-gtk-chat`:
   - evitar multiplas instancias;
   - melhorar layout;
   - adicionar historico local opcional;
   - adicionar botoes de voz/visao quando necessario.
2. Fortalecer applet:
   - health leve;
   - acoes rapidas;
   - token opcional para LAN;
   - reload automatico no instalador.
3. Separar processos:
   - `zeus-backend.service`;
   - `zeus-watcher.service`;
   - `zeus-memory.service`.
4. Atualizar CI:
   - Python;
   - Node;
   - Rust;
   - applet/chat GTK smoke checks;
   - secret scan.

## Criterio de Pronto

- Applet abre o chat GTK.
- Backend inicia via `./bin/zeus ensure-server`.
- `/api/applet/status` responde.
- Testes Python, Node e Rust passam.
- Nao ha referencias ativas aos clientes legados removidos.
