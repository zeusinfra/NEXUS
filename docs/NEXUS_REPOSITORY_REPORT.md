# Relatorio tecnico completo do repositorio NEXUS

Gerado em: 2026-05-18 20:50
Raiz analisada: `/home/nexus/Documentos/NEXUS/NEXUS`

## 1. Resumo executivo

O NEXUS e um Cognitive Operating OS local-first com interface conversacional Rust/Iced, runtime Python evidence-first, backend API Python FastAPI como runtime principal, e backend Rust/Axum como prototipo experimental, modulos Rust de alto desempenho, memoria organizacional SQLite, aprovacao humana, replay de execucao e empacotamento Debian.

O inventario rastreado pelo Git possui **486 arquivos**, aproximadamente **89,686 linhas textuais** e **41 entradas de raiz**.

### Distribuicao por categoria

| Categoria | Arquivos |
| --- | --- |
| Artefato gerado | 158 |
| Codigo Python | 143 |
| Teste | 49 |
| Codigo Rust | 31 |
| Projeto | 25 |
| Configuracao/Contrato | 23 |
| Empacotamento | 14 |
| CI/GitHub | 11 |
| Documentacao | 11 |
| Configuracao | 9 |
| Script/automacao | 6 |
| Binario/artefato | 5 |
| Codigo Go | 1 |

### Distribuicao por linguagem/formato

| Linguagem/Formato | Arquivos |
| --- | --- |
| Python | 320 |
| Texto/Binario | 45 |
| Rust | 31 |
| TOML | 22 |
| systemd | 14 |
| Markdown | 12 |
| YAML/Markdown | 11 |
| Shell | 8 |
| JSON | 6 |
| Debian package | 6 |
| Lockfile | 4 |
| Binary | 4 |
| Protocol Buffers | 1 |
| Go | 1 |
| ONNX | 1 |

## 2. Mapa das pastas

| Pasta/raiz | Arquivos | Linhas | Responsabilidade |
| --- | --- | --- | --- |
| .env.example | 1 | 138 | Arquivo ou pasta de suporte do projeto. |
| .github | 11 | 657 | Automacao GitHub: workflows de CI, Dependabot, templates de issue e pull request. |
| .gitignore | 1 | 51 | Arquivo ou pasta de suporte do projeto. |
| .gitleaks.toml | 1 | 7 | Arquivo ou pasta de suporte do projeto. |
| .trivyignore | 1 | 10 | Arquivo ou pasta de suporte do projeto. |
| CODE_OF_CONDUCT.md | 1 | 46 | Arquivo ou pasta de suporte do projeto. |
| CONTRIBUTING.md | 1 | 66 | Arquivo ou pasta de suporte do projeto. |
| LICENSE | 1 | 21 | Arquivo ou pasta de suporte do projeto. |
| Makefile | 1 | 60 | Arquivo ou pasta de suporte do projeto. |
| README.md | 1 | 160 | Arquivo ou pasta de suporte do projeto. |
| SECURITY.md | 1 | 58 | Arquivo ou pasta de suporte do projeto. |
| apps | 10 | 4,067 | Primary Python FastAPI backend and product API surface for status, cognition, privacy, web GUI and realtime hub. |
| backend | 20 | 4,097 | Experimental Rust/Axum backend prototype for future migration; not required for default runtime. |
| bin | 4 | 340 | Launchers e comandos operacionais do produto NEXUS. |
| cognitive-python | 1 | 113 | Ponte historica Python/Rust para experimentos cognitivos. |
| communication | 4 | 199 | Contrato protobuf e servicos de voz/comunicacao. |
| config | 2 | 82 | Exemplos de configuracao local e ambiente. |
| configs | 8 | 202 | Configuracoes do daemon organizacional, permissoes, identidade e unidades systemd. |
| core-rust | 24 | 3,412 | Workspace Rust de alto desempenho: sensores, memoria, seguranca, estado, politicas e bridge Python. |
| core_modules | 1 | 3 | Modulo legado do core v3. |
| deploy | 3 | 45 | Unidades systemd antigas ou alternativas para deploy. |
| dist | 158 | 28,244 | Artefatos de pacote Debian e raiz de instalacao gerada. |
| docs | 5 | 409 | Documentacao tecnica, instalacao, seguranca, arquitetura e fluxos. |
| interfaces | 3 | 519 | Interfaces alternativas, incluindo TUI Bubble Tea. |
| memory | 1 | 121 | Memoria persistida de exemplo/runtime local. |
| models | 2 | 1 | Modelos locais, especialmente voz/TTS. |
| models.txt | 1 | 1 | Arquivo ou pasta de suporte do projeto. |
| nexus-iced | 4 | 14,170 | Interface grafica Rust/Iced conversacional premium. |
| nexus_core | 124 | 25,081 | Nucleo Python: agentes, runtime verificavel, cognicao, memoria, seguranca, modelos e integracoes. |
| packaging | 14 | 213 | Fonte do empacotamento Debian, scripts, desktop entry e systemd. |
| pattern_engine.py | 1 | 98 | Arquivo ou pasta de suporte do projeto. |
| pyproject.toml | 1 | 15 | Arquivo ou pasta de suporte do projeto. |
| pytest.ini | 1 | 10 | Arquivo ou pasta de suporte do projeto. |
| requirements | 5 | 38 | Dependencias Python separadas por perfil. |
| scripts | 4 | 650 | Automacoes de desenvolvimento, bootstrap e relatorios. |
| skills | 1 | 33 | Habilidades auxiliares do sistema. |
| test_db | 5 | 0 | Banco vetorial/teste local versionado. |
| tests | 49 | 4,337 | Testes unitarios, integracao e sistema. |
| tools | 2 | 103 | Ferramentas auxiliares. |
| ui | 3 | 265 | Ativos de UI estatica. |
| watcher_rs | 4 | 1,544 | Watcher Rust para eventos de filesystem/sistema. |

## 3. Fluxos principais

### Fluxo conversacional da GUI

1. Usuario abre `nexus-iced`.
2. A sidebar minima organiza Conversas, Tarefas e Configuracoes.
3. A area central mostra chat, sugestoes e mensagens NEXUS/usuario.
4. `nexus-iced/src/websocket.rs` recebe eventos do backend ou runtime.
5. Eventos como aprovacao, output, patch, evidencia e conclusao viram mensagens ou atividades discretas.
6. A complexidade tecnica fica fora do primeiro plano; evidencia detalhada fica no runtime/CLI.

### Fluxo CLI organizacional

1. `bin/nexus` chama `nexus_core.organization.__main__`.
2. O comando carrega `NexusOrgConfig` e inicializa `OrganizationalDaemon`.
3. O daemon sincroniza agentes, blackboard, memoria SQLite, permissoes, observer e runtime.
4. Comandos como `workspace-context`, `execution-plans` e `replay-command` leem estado persistido.

### Fluxo evidence-first de comando aprovado

1. Operador propoe comando via `PermissionManager.propose_command`.
2. Politica classifica risco e cria item na approval queue.
3. Aprovacao gera `approval_id` vinculado ao hash do comando/cwd.
4. `RuntimeEngine.execute_approved` cria `command_id` e plano estruturado.
5. Resource governor avalia timeout, concorrencia, CPU/RAM e token budget.
6. Executor real captura stdout, stderr, exit code, duracao e artifacts.
7. Verification engine valida status, exit code e executor evidence.
8. Memory store persiste comando, eventos, verificacao, plano e etapas.
9. Replay builder reconstrui timeline de eventos/etapas/verificacao.
10. Se falhar, self-healing classifica a falha e registra passos de recuperacao sem aplicar patch nao aprovado.

### Fluxo de workspace memory

1. Daemon chama `WorkspaceMemory.analyze` durante inicializacao.
2. Detector busca `Cargo.toml`, `package.json`, markers Python, testes e paths relevantes.
3. Tags como `rust_project`, `iced_frontend`, `axum_backend`, `uses_sqlx` e `websocket_architecture` sao persistidas.
4. Blackboard recebe `workspace_context`; SQLite recebe entrada `scope=workspace`.
5. Planos de execucao recebem tags do workspace para melhorar contexto e auditoria.

### Fluxo de self-healing seguro

1. Falha de comando ou verificacao aciona `SelfHealingEngine.diagnose_failure`.
2. Motor analisa stdout/stderr, summary e exit code.
3. Falha e classificada como timeout, missing_command, rust_build_failure, test_failure, runtime_exception ou command_failure.
4. O sistema registra recovery steps, incidente e evento de runtime.
5. Nenhum patch ou rerun destrutivo ocorre sem nova aprovacao.

### Fluxo de empacotamento Debian

1. `make deb` chama scripts em `packaging/scripts`.
2. Arquivos sao copiados para `dist/debroot` com configuracao em `/etc/nexus` e unidade systemd.
3. Pacote final `dist/nexus_*.deb` instala `/usr/bin/nexus`, `/usr/lib/nexus`, `/var/lib/nexus` e `/var/log/nexus`.
4. Systemd executa `nexus org --config /etc/nexus/config.toml run`.

### Fluxo de CI

1. Python workflow valida lint e slices de runtime/core.
2. Rust workflow valida `core-rust`, `watcher_rs` e `nexus-iced`.
3. Security workflow roda guardrails evidence-first, Gitleaks e Trivy.
4. CodeQL cobre Actions, Python, Rust e Go.
5. Templates de issue/PR exigem evidencia, replay e respeito a budgets quando runtime for alterado.

## 4. Arquitetura por camada

| Camada | Arquivos/pastas |
| --- | --- |
| Interface humana | `nexus-iced`, `interfaces/tui-bubbletea`, `ui/static`, `apps/web_gui.py` |
| Produto/CLI | `bin/nexus`, `nexus_core/product_cli.py`, `nexus_core/organization/__main__.py` |
| Runtime organizacional | `nexus_core/organization/*` |
| Execucao evidence-first | `nexus_core/execution_protocol.py`, `nexus_core/organization/runtime.py` |
| Memoria | `nexus_core/organization/memory.py`, `nexus_core/conversation/*`, `memory/*` |
| Cognicao | `nexus_core/cognitive/*`, `nexus_core/v4/*` |
| Modelos | `nexus_core/models/*`, `nexus_core/model_router.py`, `nexus_core/llm_service.py` |
| Backend Rust | `backend/src/*` |
| Rust acelerado | `core-rust/*`, `watcher_rs/*` |
| Entrega | `packaging/*`, `dist/*`, `deploy/systemd/*`, `configs/systemd/*` |
| Qualidade | `tests/*`, `.github/workflows/*`, `.github/ISSUE_TEMPLATE/*` |

## 5. Detalhamento por pasta

### .env.example

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 138. Tamanho total: 4.1 KB.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 1 |

### .github

Automacao GitHub: workflows de CI, Dependabot, templates de issue e pull request.

Arquivos: 11. Linhas textuais aproximadas: 657. Tamanho total: 17.1 KB.

| Tipo | Quantidade |
| --- | --- |
| CI/GitHub | 11 |

### .gitignore

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 51. Tamanho total: 580 B.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 1 |

### .gitleaks.toml

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 7. Tamanho total: 210 B.

| Tipo | Quantidade |
| --- | --- |
| Configuracao/Contrato | 1 |

### .trivyignore

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 10. Tamanho total: 385 B.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 1 |

### CODE_OF_CONDUCT.md

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 46. Tamanho total: 2.5 KB.

| Tipo | Quantidade |
| --- | --- |
| Documentacao | 1 |

### CONTRIBUTING.md

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 66. Tamanho total: 3.1 KB.

| Tipo | Quantidade |
| --- | --- |
| Documentacao | 1 |

### LICENSE

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 21. Tamanho total: 1.1 KB.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 1 |

### Makefile

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 60. Tamanho total: 1.5 KB.

| Tipo | Quantidade |
| --- | --- |
| Script/automacao | 1 |

Arquivos-chave:

- `Makefile`: Atalhos de build, teste e empacotamento.

### README.md

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 160. Tamanho total: 6.7 KB.

| Tipo | Quantidade |
| --- | --- |
| Documentacao | 1 |

Arquivos-chave:

- `README.md`: Entrada principal do projeto e visao de produto.

### SECURITY.md

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 58. Tamanho total: 3.0 KB.

| Tipo | Quantidade |
| --- | --- |
| Documentacao | 1 |

### apps

Superficie FastAPI e rotas de produto para status, cognicao, privacidade, GUI web e hub em tempo real.

Arquivos: 10. Linhas textuais aproximadas: 4,067. Tamanho total: 141.4 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Python | 10 |

### backend

Backend Rust/Axum para eventos, aprovacoes, execucao, filesystem, gateway, LLM, storage e workers.

Arquivos: 20. Linhas textuais aproximadas: 4,097. Tamanho total: 153.4 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Rust | 16 |
| Projeto | 3 |
| Configuracao/Contrato | 1 |

Arquivos-chave:

- `backend/src/approvals/mod.rs`: Fluxo de aprovacao do backend Rust.
- `backend/src/execution/command.rs`: Execucao de comandos no backend Rust.
- `backend/src/execution/graph.rs`: Grafo de tarefas/execucao do backend Rust.
- `backend/src/execution/patch.rs`: Aplicacao/preview de patches no backend Rust.
- `backend/src/main.rs`: Entrada do backend Rust/Axum.

### bin

Launchers e comandos operacionais do produto NEXUS.

Arquivos: 4. Linhas textuais aproximadas: 340. Tamanho total: 12.3 KB.

| Tipo | Quantidade |
| --- | --- |
| Script/automacao | 2 |
| Projeto | 1 |
| Configuracao/Contrato | 1 |

Arquivos-chave:

- `bin/nexus`: Launcher unificado para CLI de produto e organizacao.

### cognitive-python

Ponte historica Python/Rust para experimentos cognitivos.

Arquivos: 1. Linhas textuais aproximadas: 113. Tamanho total: 3.9 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Python | 1 |

### communication

Contrato protobuf e servicos de voz/comunicacao.

Arquivos: 4. Linhas textuais aproximadas: 199. Tamanho total: 5.8 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Python | 3 |
| Configuracao/Contrato | 1 |

### config

Exemplos de configuracao local e ambiente.

Arquivos: 2. Linhas textuais aproximadas: 82. Tamanho total: 2.0 KB.

| Tipo | Quantidade |
| --- | --- |
| Configuracao | 2 |

### configs

Configuracoes do daemon organizacional, permissoes, identidade e unidades systemd.

Arquivos: 8. Linhas textuais aproximadas: 202. Tamanho total: 6.7 KB.

| Tipo | Quantidade |
| --- | --- |
| Configuracao | 7 |
| Documentacao | 1 |

### core-rust

Workspace Rust de alto desempenho: sensores, memoria, seguranca, estado, politicas e bridge Python.

Arquivos: 24. Linhas textuais aproximadas: 3,412. Tamanho total: 90.4 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Rust | 12 |
| Configuracao/Contrato | 10 |
| Projeto | 2 |

Arquivos-chave:

- `core-rust/nexus_sensors/src/lib.rs`: Sensores Rust de OS/processos/filesystem.
- `core-rust/nexus_synapse/src/lib.rs`: Bridge Rust/PyO3 para memoria sinaptica.

### core_modules

Modulo legado do core v3.

Arquivos: 1. Linhas textuais aproximadas: 3. Tamanho total: 114 B.

| Tipo | Quantidade |
| --- | --- |
| Codigo Python | 1 |

### deploy

Unidades systemd antigas ou alternativas para deploy.

Arquivos: 3. Linhas textuais aproximadas: 45. Tamanho total: 1.3 KB.

| Tipo | Quantidade |
| --- | --- |
| Configuracao/Contrato | 3 |

### dist

Artefatos de pacote Debian e raiz de instalacao gerada.

Arquivos: 158. Linhas textuais aproximadas: 28,244. Tamanho total: 3.8 MB.

| Tipo | Quantidade |
| --- | --- |
| Artefato gerado | 158 |

### docs

Documentacao tecnica, instalacao, seguranca, arquitetura e fluxos.

Arquivos: 5. Linhas textuais aproximadas: 409. Tamanho total: 13.0 KB.

| Tipo | Quantidade |
| --- | --- |
| Documentacao | 5 |

### interfaces

Interfaces alternativas, incluindo TUI Bubble Tea.

Arquivos: 3. Linhas textuais aproximadas: 519. Tamanho total: 13.9 KB.

| Tipo | Quantidade |
| --- | --- |
| Documentacao | 1 |
| Projeto | 1 |
| Codigo Go | 1 |

Arquivos-chave:

- `interfaces/tui-bubbletea/main.go`: TUI Bubble Tea para observabilidade operacional.

### memory

Memoria persistida de exemplo/runtime local.

Arquivos: 1. Linhas textuais aproximadas: 121. Tamanho total: 3.1 KB.

| Tipo | Quantidade |
| --- | --- |
| Configuracao/Contrato | 1 |

### models

Modelos locais, especialmente voz/TTS.

Arquivos: 2. Linhas textuais aproximadas: 1. Tamanho total: 58 B.

| Tipo | Quantidade |
| --- | --- |
| Binario/artefato | 1 |
| Configuracao/Contrato | 1 |

### models.txt

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 1. Tamanho total: 1.9 KB.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 1 |

### nexus-iced

Interface grafica Rust/Iced conversacional premium.

Arquivos: 4. Linhas textuais aproximadas: 14,170. Tamanho total: 429.1 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Rust | 2 |
| Projeto | 1 |
| Configuracao/Contrato | 1 |

Arquivos-chave:

- `nexus-iced/src/main.rs`: GUI Rust/Iced principal.
- `nexus-iced/src/websocket.rs`: Cliente/eventos WebSocket da GUI.

### nexus_core

Nucleo Python: agentes, runtime verificavel, cognicao, memoria, seguranca, modelos e integracoes.

Arquivos: 124. Linhas textuais aproximadas: 25,081. Tamanho total: 832.3 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Python | 124 |

Arquivos-chave:

- `nexus_core/execution_protocol.py`: Ledger e protocolo evidence-first para execucao real de comandos.
- `nexus_core/model_router.py`: Roteamento local/cloud por complexidade e risco.
- `nexus_core/organization/daemon.py`: Daemon persistente que integra memoria, blackboard, permissoes, swarm, runtime e workspace context.
- `nexus_core/organization/execution_plans.py`: Plano estruturado de execucao e etapas auditaveis.
- `nexus_core/organization/memory.py`: SQLite organizacional para tarefas, decisoes, eventos, comandos, verificacoes, planos e replays.
- `nexus_core/organization/replay.py`: Reconstrucao de timeline de comando ou tarefa.
- `nexus_core/organization/resource_budget.py`: Orcamento de CPU/RAM/timeout/concorrencia/tokens para autonomia segura.
- `nexus_core/organization/runtime.py`: Runtime de execucao verificavel com planos, budgets, evidencia, replay e self-healing.
- `nexus_core/organization/security.py`: Politica, fila de aprovacao e fronteira entre proposta/aprovacao/execucao.
- `nexus_core/organization/self_healing.py`: Diagnostico de falhas e passos de recuperacao seguros.
- `nexus_core/organization/workspace_context.py`: Detector de traits do workspace.
- `nexus_core/product_cli.py`: CLI de produto Linux para status, modelos e roteamento.

### packaging

Fonte do empacotamento Debian, scripts, desktop entry e systemd.

Arquivos: 14. Linhas textuais aproximadas: 213. Tamanho total: 6.2 KB.

| Tipo | Quantidade |
| --- | --- |
| Empacotamento | 14 |

Arquivos-chave:

- `packaging/scripts/build_deb.sh`: Build deterministico do pacote Debian.

### pattern_engine.py

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 98. Tamanho total: 3.1 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Python | 1 |

### pyproject.toml

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 15. Tamanho total: 299 B.

| Tipo | Quantidade |
| --- | --- |
| Configuracao/Contrato | 1 |

Arquivos-chave:

- `pyproject.toml`: Configuracao de lint, formatacao e type checking Python.

### pytest.ini

Raiz de suporte ou arquivo solto do projeto.

Arquivos: 1. Linhas textuais aproximadas: 10. Tamanho total: 342 B.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 1 |

Arquivos-chave:

- `pytest.ini`: Configuracao global do pytest.

### requirements

Dependencias Python separadas por perfil.

Arquivos: 5. Linhas textuais aproximadas: 38. Tamanho total: 808 B.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 5 |

### scripts

Automacoes de desenvolvimento, bootstrap e relatorios.

Arquivos: 4. Linhas textuais aproximadas: 650. Tamanho total: 21.1 KB.

| Tipo | Quantidade |
| --- | --- |
| Script/automacao | 2 |
| Codigo Python | 1 |
| Configuracao/Contrato | 1 |

### skills

Habilidades auxiliares do sistema.

Arquivos: 1. Linhas textuais aproximadas: 33. Tamanho total: 1.2 KB.

| Tipo | Quantidade |
| --- | --- |
| Codigo Python | 1 |

### test_db

Banco vetorial/teste local versionado.

Arquivos: 5. Linhas textuais aproximadas: 0. Tamanho total: 199.3 KB.

| Tipo | Quantidade |
| --- | --- |
| Binario/artefato | 4 |
| Projeto | 1 |

### tests

Testes unitarios, integracao e sistema.

Arquivos: 49. Linhas textuais aproximadas: 4,337. Tamanho total: 148.7 KB.

| Tipo | Quantidade |
| --- | --- |
| Teste | 49 |

### tools

Ferramentas auxiliares.

Arquivos: 2. Linhas textuais aproximadas: 103. Tamanho total: 2.9 KB.

| Tipo | Quantidade |
| --- | --- |
| Script/automacao | 1 |
| Codigo Python | 1 |

### ui

Ativos de UI estatica.

Arquivos: 3. Linhas textuais aproximadas: 265. Tamanho total: 9.9 KB.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 3 |

### watcher_rs

Watcher Rust para eventos de filesystem/sistema.

Arquivos: 4. Linhas textuais aproximadas: 1,544. Tamanho total: 39.7 KB.

| Tipo | Quantidade |
| --- | --- |
| Projeto | 2 |
| Configuracao/Contrato | 1 |
| Codigo Rust | 1 |

## 6. Inventario completo de arquivos

Tabela completa dos arquivos rastreados pelo Git. Linhas vazias indicam arquivo binario, lockfile ou artefato.

| Arquivo | Categoria | Formato | Linhas | Tamanho | Descricao |
| --- | --- | --- | --- | --- | --- |
| .env.example | Projeto | Texto/Binario | 138 | 4.1 KB | Projeto em formato Texto/Binario. |
| .github/ISSUE_TEMPLATE/bug_report.yml | CI/GitHub | YAML/Markdown | 41 | 1.3 KB | Template GitHub Issue bug_report.yml. |
| .github/ISSUE_TEMPLATE/feature_request.yml | CI/GitHub | YAML/Markdown | 41 | 1.3 KB | Template GitHub Issue feature_request.yml. |
| .github/PULL_REQUEST_TEMPLATE.md | CI/GitHub | YAML/Markdown | 20 | 932 B | CI/GitHub em formato YAML/Markdown. |
| .github/dependabot.yml | CI/GitHub | YAML/Markdown | 49 | 972 B | CI/GitHub em formato YAML/Markdown. |
| .github/workflows/ai-stack.yml | CI/GitHub | YAML/Markdown | 63 | 1.6 KB | Workflow CI ai-stack.yml. |
| .github/workflows/browser-stack.yml | CI/GitHub | YAML/Markdown | 59 | 1.5 KB | Workflow CI browser-stack.yml. |
| .github/workflows/codeql.yml | CI/GitHub | YAML/Markdown | 58 | 1.3 KB | Workflow CI codeql.yml. |
| .github/workflows/python.yml | CI/GitHub | YAML/Markdown | 94 | 2.6 KB | Workflow CI python.yml. |
| .github/workflows/rust.yml | CI/GitHub | YAML/Markdown | 92 | 2.0 KB | Workflow CI rust.yml. |
| .github/workflows/security.yml | CI/GitHub | YAML/Markdown | 81 | 2.1 KB | Workflow CI security.yml. |
| .github/workflows/voice-stack.yml | CI/GitHub | YAML/Markdown | 59 | 1.5 KB | Workflow CI voice-stack.yml. |
| .gitignore | Projeto | Texto/Binario | 51 | 580 B | Projeto em formato Texto/Binario. |
| .gitleaks.toml | Configuracao/Contrato | TOML | 7 | 210 B | Configuracao/Contrato em formato TOML. |
| .trivyignore | Projeto | Texto/Binario | 10 | 385 B | Projeto em formato Texto/Binario. |
| CODE_OF_CONDUCT.md | Documentacao | Markdown | 46 | 2.5 KB | Documentacao em formato Markdown. |
| CONTRIBUTING.md | Documentacao | Markdown | 66 | 3.1 KB | Documentacao em formato Markdown. |
| LICENSE | Projeto | Texto/Binario | 21 | 1.1 KB | Projeto em formato Texto/Binario. |
| Makefile | Script/automacao | Texto/Binario | 60 | 1.5 KB | Atalhos de build, teste e empacotamento. |
| README.md | Documentacao | Markdown | 160 | 6.7 KB | Entrada principal do projeto e visao de produto. |
| SECURITY.md | Documentacao | Markdown | 58 | 3.0 KB | Documentacao em formato Markdown. |
| apps/__init__.py | Codigo Python | Python | 1 | 0 B | Inicializador de pacote Python. |
| apps/lifecycle_manager.py | Codigo Python | Python | 153 | 6.0 KB | Modulo Python `lifecycle manager`. |
| apps/nexus_evolution.py | Codigo Python | Python | 110 | 4.3 KB | Modulo Python `nexus evolution`. |
| apps/nexus_v4.py | Codigo Python | Python | 14 | 248 B | Modulo Python `nexus v4`. |
| apps/realtime_hub.py | Codigo Python | Python | 205 | 7.7 KB | Modulo Python `realtime hub`. |
| apps/routes/__init__.py | Codigo Python | Python | 1 | 48 B | Inicializador de pacote Python. |
| apps/routes/cognition_routes.py | Codigo Python | Python | 162 | 6.3 KB | Modulo Python `cognition routes`. |
| apps/routes/privacy_routes.py | Codigo Python | Python | 68 | 2.0 KB | Modulo Python `privacy routes`. |
| apps/status_routes.py | Codigo Python | Python | 116 | 4.0 KB | Modulo Python `status routes`. |
| apps/web_gui.py | Codigo Python | Python | 3237 | 110.7 KB | Modulo Python `web gui`. |
| backend/Cargo.lock | Projeto | Lockfile | 3002 | 72.6 KB | Lockfile Cargo com dependencias Rust resolvidas. |
| backend/Cargo.toml | Configuracao/Contrato | TOML | 36 | 860 B | Manifesto Cargo do crate/workspace Rust. |
| backend/nexus_backend.db-shm | Projeto | Texto/Binario |  | 32.0 KB | Projeto em formato Texto/Binario. |
| backend/nexus_backend.db-wal | Projeto | Texto/Binario |  | 12.1 KB | Projeto em formato Texto/Binario. |
| backend/src/approvals/mod.rs | Codigo Rust | Rust | 47 | 1.4 KB | Fluxo de aprovacao do backend Rust. |
| backend/src/events/mod.rs | Codigo Rust | Rust | 61 | 2.0 KB | Modulo Rust `mod`. |
| backend/src/execution/command.rs | Codigo Rust | Rust | 89 | 2.9 KB | Execucao de comandos no backend Rust. |
| backend/src/execution/graph.rs | Codigo Rust | Rust | 104 | 3.3 KB | Grafo de tarefas/execucao do backend Rust. |
| backend/src/execution/mod.rs | Codigo Rust | Rust | 5 | 75 B | Modulo Rust `mod`. |
| backend/src/execution/patch.rs | Codigo Rust | Rust | 89 | 3.1 KB | Aplicacao/preview de patches no backend Rust. |
| backend/src/execution/risk.rs | Codigo Rust | Rust | 93 | 3.0 KB | Modulo Rust `risk`. |
| backend/src/execution/test.rs | Codigo Rust | Rust | 36 | 1.0 KB | Modulo Rust `test`. |
| backend/src/filesystem/mod.rs | Codigo Rust | Rust | 50 | 1.9 KB | Modulo Rust `mod`. |
| backend/src/gateway/mod.rs | Codigo Rust | Rust | 115 | 3.6 KB | Modulo Rust `mod`. |
| backend/src/llm/mod.rs | Codigo Rust | Rust | 138 | 6.5 KB | Modulo Rust `mod`. |
| backend/src/main.rs | Codigo Rust | Rust | 71 | 2.0 KB | Entrada do backend Rust/Axum. |
| backend/src/state/mod.rs | Codigo Rust | Rust | 46 | 1.5 KB | Modulo Rust `mod`. |
| backend/src/storage/mod.rs | Codigo Rust | Rust | 81 | 2.6 KB | Modulo Rust `mod`. |
| backend/src/telemetry/mod.rs | Codigo Rust | Rust | 11 | 380 B | Modulo Rust `mod`. |
| backend/src/workers/mod.rs | Codigo Rust | Rust | 23 | 715 B | Modulo Rust `mod`. |
| bin/install-lifetime.sh | Script/automacao | Shell | 57 | 2.4 KB | Script/automacao em formato Shell. |
| bin/nexus | Projeto | Texto/Binario | 246 | 8.9 KB | Launcher unificado para CLI de produto e organizacao. |
| bin/nexus_core.service | Configuracao/Contrato | systemd | 20 | 513 B | Unidade systemd para daemonizacao. |
| bin/start_ai.sh | Script/automacao | Shell | 17 | 559 B | Script/automacao em formato Shell. |
| cognitive-python/rust_connect.py | Codigo Python | Python | 113 | 3.9 KB | Modulo Python `rust connect`. |
| communication/__init__.py | Codigo Python | Python | 1 | 7 B | Inicializador de pacote Python. |
| communication/build_proto.py | Codigo Python | Python | 26 | 646 B | Modulo Python `build proto`. |
| communication/nexus_core.proto | Configuracao/Contrato | Protocol Buffers | 70 | 1.4 KB | Configuracao/Contrato em formato Protocol Buffers. |
| communication/voice_service.py | Codigo Python | Python | 102 | 3.7 KB | Modulo Python `voice service`. |
| config/config.example.toml | Configuracao | TOML | 73 | 1.7 KB | Configuracao em formato TOML. |
| config/nexus.env.example | Configuracao | Texto/Binario | 9 | 293 B | Configuracao em formato Texto/Binario. |
| configs/README.md | Documentacao | Markdown | 37 | 1.5 KB | Documentacao em formato Markdown. |
| configs/goals_v4.json | Configuracao | JSON | 13 | 255 B | Configuracao em formato JSON. |
| configs/identity.json | Configuracao | JSON | 46 | 1.7 KB | Configuracao em formato JSON. |
| configs/nexus.toml | Configuracao | TOML | 28 | 662 B | Configuracao em formato TOML. |
| configs/permissions.toml | Configuracao | TOML | 16 | 444 B | Configuracao em formato TOML. |
| configs/systemd/nexus-core.service | Configuracao | systemd | 25 | 863 B | Unidade systemd para daemonizacao. |
| configs/systemd/nexus-organization.service | Configuracao | systemd | 20 | 732 B | Unidade systemd para daemonizacao. |
| configs/systemd/nexus-watcher.service | Configuracao | systemd | 17 | 632 B | Unidade systemd para daemonizacao. |
| core-rust/.gitignore | Projeto | Texto/Binario | 1 | 8 B | Projeto em formato Texto/Binario. |
| core-rust/Cargo.lock | Projeto | Lockfile | 1402 | 34.0 KB | Lockfile Cargo com dependencias Rust resolvidas. |
| core-rust/Cargo.toml | Configuracao/Contrato | TOML | 18 | 288 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/build.rs | Codigo Rust | Rust | 9 | 326 B | Modulo Rust `build`. |
| core-rust/nexus_cognitive/Cargo.toml | Configuracao/Contrato | TOML | 16 | 339 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_cognitive/src/lib.rs | Codigo Rust | Rust | 142 | 3.8 KB | Modulo Rust `lib`. |
| core-rust/nexus_memory/Cargo.toml | Configuracao/Contrato | TOML | 25 | 533 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_memory/src/lib.rs | Codigo Rust | Rust | 130 | 3.3 KB | Modulo Rust `lib`. |
| core-rust/nexus_memory/src/main.rs | Codigo Rust | Rust | 89 | 2.4 KB | Modulo Rust `main`. |
| core-rust/nexus_patterns/Cargo.toml | Configuracao/Contrato | TOML | 17 | 388 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_patterns/src/lib.rs | Codigo Rust | Rust | 100 | 2.5 KB | Modulo Rust `lib`. |
| core-rust/nexus_policy/Cargo.toml | Configuracao/Contrato | TOML | 17 | 348 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_policy/src/lib.rs | Codigo Rust | Rust | 420 | 12.4 KB | Modulo Rust `lib`. |
| core-rust/nexus_security/Cargo.toml | Configuracao/Contrato | TOML | 17 | 352 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_security/src/lib.rs | Codigo Rust | Rust | 127 | 3.4 KB | Modulo Rust `lib`. |
| core-rust/nexus_sensors/Cargo.toml | Configuracao/Contrato | TOML | 18 | 368 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_sensors/src/lib.rs | Codigo Rust | Rust | 264 | 7.3 KB | Sensores Rust de OS/processos/filesystem. |
| core-rust/nexus_state/Cargo.toml | Configuracao/Contrato | TOML | 18 | 364 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_state/src/lib.rs | Codigo Rust | Rust | 81 | 2.1 KB | Modulo Rust `lib`. |
| core-rust/nexus_synapse/Cargo.toml | Configuracao/Contrato | TOML | 18 | 442 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_synapse/src/lib.rs | Codigo Rust | Rust | 138 | 5.1 KB | Bridge Rust/PyO3 para memoria sinaptica. |
| core-rust/nexus_sync/Cargo.toml | Configuracao/Contrato | TOML | 16 | 329 B | Manifesto Cargo do crate/workspace Rust. |
| core-rust/nexus_sync/src/lib.rs | Codigo Rust | Rust | 98 | 2.8 KB | Modulo Rust `lib`. |
| core-rust/src/main.rs | Codigo Rust | Rust | 231 | 7.4 KB | Modulo Rust `main`. |
| core_modules/nexus_core_v3.py | Codigo Python | Python | 3 | 114 B | Modulo Python `nexus core v3`. |
| deploy/systemd/nexus-cognition.service | Configuracao/Contrato | systemd | 14 | 371 B | Unidade systemd para daemonizacao. |
| deploy/systemd/nexus-root-daemon.service | Configuracao/Contrato | systemd | 16 | 516 B | Unidade systemd para daemonizacao. |
| deploy/systemd/nexus.service | Configuracao/Contrato | systemd | 15 | 461 B | Unidade systemd para daemonizacao. |
| dist/debroot/DEBIAN/conffiles | Artefato gerado | Texto/Binario | 2 | 44 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/DEBIAN/control | Artefato gerado | Texto/Binario | 12 | 485 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/DEBIAN/postinst | Artefato gerado | Texto/Binario | 37 | 831 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/DEBIAN/postrm | Artefato gerado | Texto/Binario | 8 | 109 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/DEBIAN/prerm | Artefato gerado | Texto/Binario | 8 | 130 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/etc/nexus/config.toml | Artefato gerado | TOML | 73 | 1.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/etc/nexus/nexus.env | Artefato gerado | Texto/Binario | 9 | 293 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/lib/systemd/system/nexus.service | Artefato gerado | systemd | 30 | 814 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/bin/nexus | Artefato gerado | Texto/Binario | 4 | 91 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/__init__.py | Artefato gerado | Python | 1 | 0 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/lifecycle_manager.py | Artefato gerado | Python | 153 | 6.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/nexus_evolution.py | Artefato gerado | Python | 110 | 4.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/nexus_v4.py | Artefato gerado | Python | 14 | 248 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/realtime_hub.py | Artefato gerado | Python | 205 | 7.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/routes/__init__.py | Artefato gerado | Python | 1 | 48 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/routes/cognition_routes.py | Artefato gerado | Python | 162 | 6.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/routes/privacy_routes.py | Artefato gerado | Python | 68 | 2.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/status_routes.py | Artefato gerado | Python | 116 | 4.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/apps/web_gui.py | Artefato gerado | Python | 3023 | 103.6 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/bin/install-lifetime.sh | Artefato gerado | Shell | 57 | 2.4 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/bin/nexus | Artefato gerado | Texto/Binario | 246 | 8.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/bin/nexus_core.service | Artefato gerado | systemd | 20 | 513 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/bin/start_ai.sh | Artefato gerado | Shell | 17 | 559 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/config/config.example.toml | Artefato gerado | TOML | 73 | 1.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/config/nexus.env.example | Artefato gerado | Texto/Binario | 9 | 293 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/README.md | Artefato gerado | Markdown | 28 | 1.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/goals_v4.json | Artefato gerado | JSON | 13 | 255 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/identity.json | Artefato gerado | JSON | 46 | 1.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/nexus.toml | Artefato gerado | TOML | 28 | 662 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/permissions.toml | Artefato gerado | TOML | 16 | 444 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/systemd/nexus-core.service | Artefato gerado | systemd | 25 | 863 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/systemd/nexus-organization.service | Artefato gerado | systemd | 20 | 732 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/configs/systemd/nexus-watcher.service | Artefato gerado | systemd | 17 | 632 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/__init__.py | Artefato gerado | Python | 5 | 79 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/actions.py | Artefato gerado | Python | 514 | 18.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/actions_registry.py | Artefato gerado | Python | 38 | 947 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/agent.py | Artefato gerado | Python | 1148 | 37.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/architect_agent.py | Artefato gerado | Python | 107 | 4.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/asr.py | Artefato gerado | Python | 113 | 3.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/boot_diagnostics.py | Artefato gerado | Python | 51 | 1.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/browser_control.py | Artefato gerado | Python | 165 | 5.4 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/__init__.py | Artefato gerado | Python | 13 | 300 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/__main__.py | Artefato gerado | Python | 5 | 123 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/attention_engine.py | Artefato gerado | Python | 249 | 8.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/classifier.py | Artefato gerado | Python | 67 | 2.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/cognition_service.py | Artefato gerado | Python | 131 | 4.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/cognitive_db.py | Artefato gerado | Python | 255 | 8.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/cognitive_loop.py | Artefato gerado | Python | 715 | 27.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/cognitive_state.py | Artefato gerado | Python | 126 | 4.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/context_engine.py | Artefato gerado | Python | 89 | 2.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/execution_engine.py | Artefato gerado | Python | 325 | 10.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/goal_engine.py | Artefato gerado | Python | 277 | 9.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/learning_engine.py | Artefato gerado | Python | 259 | 8.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/memory_compression.py | Artefato gerado | Python | 173 | 6.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/planner.py | Artefato gerado | Python | 326 | 10.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/predictive_engine.py | Artefato gerado | Python | 113 | 3.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/priority_orchestrator.py | Artefato gerado | Python | 165 | 5.4 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/reflection_engine.py | Artefato gerado | Python | 357 | 12.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/self_healing.py | Artefato gerado | Python | 116 | 3.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/simulator.py | Artefato gerado | Python | 217 | 7.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/cognitive/user_profile_engine.py | Artefato gerado | Python | 764 | 26.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/command_policy.py | Artefato gerado | Python | 295 | 7.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/config_guard.py | Artefato gerado | Python | 138 | 4.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/conversation/context_builder.py | Artefato gerado | Python | 94 | 3.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/conversation/conversation_manager.py | Artefato gerado | Python | 59 | 2.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/conversation/response_sanitizer.py | Artefato gerado | Python | 58 | 1.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/conversation/sqlite_conversation_memory.py | Artefato gerado | Python | 183 | 5.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/conversation/topic_tracker.py | Artefato gerado | Python | 58 | 2.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/conversation/turn_store.py | Artefato gerado | Python | 86 | 2.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/core_system.py | Artefato gerado | Python | 771 | 26.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/diagnostics.py | Artefato gerado | Python | 79 | 2.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/env.py | Artefato gerado | Python | 23 | 684 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/event_pipeline.py | Artefato gerado | Python | 107 | 3.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/events/event_bus.py | Artefato gerado | Python | 232 | 7.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/events/sync_engine.py | Artefato gerado | Python | 355 | 12.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/events/sync_worker.py | Artefato gerado | Python | 78 | 2.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/events/watcher.py | Artefato gerado | Python | 77 | 2.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/execution_engine.py | Artefato gerado | Python | 125 | 4.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/execution_protocol.py | Artefato gerado | Python | 810 | 26.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/executive_agent.py | Artefato gerado | Python | 101 | 3.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/executor.py | Artefato gerado | Python | 129 | 4.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/health_status.py | Artefato gerado | Python | 138 | 4.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/integrations/filesystem_mirror.py | Artefato gerado | Python | 190 | 7.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/integrations/linear.py | Artefato gerado | Python | 207 | 5.6 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/integrations/notion.py | Artefato gerado | Python | 232 | 7.6 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/integrations/obsidian.py | Artefato gerado | Python | 123 | 4.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/interaction/interaction_engine.py | Artefato gerado | Python | 68 | 2.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/learning_engine.py | Artefato gerado | Python | 112 | 4.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/llm_service.py | Artefato gerado | Python | 63 | 1.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/long_term_memory.py | Artefato gerado | Python | 191 | 5.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/memory/context_manager.py | Artefato gerado | Python | 57 | 1.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/memory/sqlite_memory.py | Artefato gerado | Python | 272 | 7.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/memory_hierarchy.py | Artefato gerado | Python | 96 | 3.6 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/memory_manager.py | Artefato gerado | Python | 427 | 14.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/model_router.py | Artefato gerado | Python | 102 | 2.6 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/models/__init__.py | Artefato gerado | Python | 3 | 143 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/models/base_model_client.py | Artefato gerado | Python | 21 | 414 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/models/cloud_client.py | Artefato gerado | Python | 42 | 1.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/models/model_registry.py | Artefato gerado | Python | 23 | 740 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/models/ollama_client.py | Artefato gerado | Python | 184 | 5.4 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/nexus_core_v3.py | Artefato gerado | Python | 189 | 6.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/observability.py | Artefato gerado | Python | 111 | 3.4 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/__init__.py | Artefato gerado | Python | 36 | 1.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/__main__.py | Artefato gerado | Python | 313 | 11.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/agents.py | Artefato gerado | Python | 248 | 7.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/blackboard.py | Artefato gerado | Python | 236 | 7.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/config.py | Artefato gerado | Python | 164 | 5.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/continuous.py | Artefato gerado | Python | 100 | 3.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/daemon.py | Artefato gerado | Python | 242 | 8.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/health.py | Artefato gerado | Python | 263 | 7.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/memory.py | Artefato gerado | Python | 1132 | 40.4 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/observer.py | Artefato gerado | Python | 181 | 6.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/runtime.py | Artefato gerado | Python | 234 | 8.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/security.py | Artefato gerado | Python | 345 | 11.6 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/swarm.py | Artefato gerado | Python | 334 | 11.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/organization/verification.py | Artefato gerado | Python | 140 | 4.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/path_filters.py | Artefato gerado | Python | 66 | 1.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/peripherals/bluetooth_monitor.py | Artefato gerado | Python | 95 | 3.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/peripherals/usb_monitor.py | Artefato gerado | Python | 323 | 11.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/planner.py | Artefato gerado | Python | 121 | 3.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/product_cli.py | Artefato gerado | Python | 484 | 15.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/recovery_engine.py | Artefato gerado | Python | 87 | 3.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/resource_control.py | Artefato gerado | Python | 90 | 3.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/response_text.py | Artefato gerado | Python | 218 | 6.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/rust_sensors.py | Artefato gerado | Python | 73 | 2.1 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/security/daemon_client.py | Artefato gerado | Python | 143 | 4.6 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/security/privacy_guard.py | Artefato gerado | Python | 322 | 10.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/security/root_daemon.py | Artefato gerado | Python | 855 | 28.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/security_guard.py | Artefato gerado | Python | 143 | 3.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/self_improvement/audit_log.py | Artefato gerado | Python | 67 | 1.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/self_improvement/patch_manager.py | Artefato gerado | Python | 55 | 1.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/self_improvement/pipeline.py | Artefato gerado | Python | 135 | 5.0 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/self_improvement/rollback_manager.py | Artefato gerado | Python | 36 | 1.2 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/sentry_observability.py | Artefato gerado | Python | 101 | 2.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/simulation_layer.py | Artefato gerado | Python | 111 | 3.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/skill_engine.py | Artefato gerado | Python | 51 | 1.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/synaptic_sync.py | Artefato gerado | Python | 68 | 2.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/tools.py | Artefato gerado | Python | 178 | 5.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/__init__.py | Artefato gerado | Python | 1 | 49 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/core.py | Artefato gerado | Python | 230 | 7.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/executor.py | Artefato gerado | Python | 259 | 8.3 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/goals.py | Artefato gerado | Python | 122 | 3.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/guardian.py | Artefato gerado | Python | 109 | 3.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/memory.py | Artefato gerado | Python | 87 | 2.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/planner.py | Artefato gerado | Python | 149 | 4.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/reward.py | Artefato gerado | Python | 35 | 917 B | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/sensors.py | Artefato gerado | Python | 181 | 5.7 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/v4/types.py | Artefato gerado | Python | 91 | 1.8 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/vector_memory.py | Artefato gerado | Python | 195 | 6.4 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/vision.py | Artefato gerado | Python | 177 | 5.5 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/lib/nexus/nexus_core/voice_sensing.py | Artefato gerado | Python | 568 | 20.9 KB | Arquivo copiado para a raiz Debian gerada. |
| dist/debroot/usr/share/applications/nexus.desktop | Artefato gerado | Texto/Binario | 7 | 157 B | Arquivo copiado para a raiz Debian gerada. |
| dist/nexus_0.1.0_amd64.deb | Artefato gerado | Debian package |  | 489.9 KB | Artefato gerado em formato Debian package. |
| dist/nexus_0.1.1_amd64.deb | Artefato gerado | Debian package |  | 492.0 KB | Artefato gerado em formato Debian package. |
| dist/nexus_0.1.2_amd64.deb | Artefato gerado | Debian package |  | 492.4 KB | Artefato gerado em formato Debian package. |
| dist/nexus_0.1.3_amd64.deb | Artefato gerado | Debian package |  | 492.5 KB | Artefato gerado em formato Debian package. |
| dist/nexus_0.1.4_amd64.deb | Artefato gerado | Debian package |  | 492.8 KB | Artefato gerado em formato Debian package. |
| dist/nexus_0.1.5_amd64.deb | Artefato gerado | Debian package |  | 496.1 KB | Artefato gerado em formato Debian package. |
| docs/ARCHITECTURE.md | Documentacao | Markdown | 92 | 3.2 KB | Documentacao em formato Markdown. |
| docs/FLOWCHART.md | Documentacao | Markdown | 114 | 4.0 KB | Documentacao em formato Markdown. |
| docs/INSTALL.md | Documentacao | Markdown | 90 | 2.3 KB | Documentacao em formato Markdown. |
| docs/PACKAGE.md | Documentacao | Markdown | 67 | 1.7 KB | Documentacao em formato Markdown. |
| docs/SECURITY.md | Documentacao | Markdown | 46 | 1.7 KB | Documentacao em formato Markdown. |
| interfaces/tui-bubbletea/README.md | Documentacao | Markdown | 44 | 1.7 KB | Documentacao em formato Markdown. |
| interfaces/tui-bubbletea/go.mod | Projeto | Texto/Binario | 9 | 167 B | Projeto em formato Texto/Binario. |
| interfaces/tui-bubbletea/main.go | Codigo Go | Go | 466 | 12.1 KB | TUI Bubble Tea para observabilidade operacional. |
| memory/long_term.json | Configuracao/Contrato | JSON | 121 | 3.1 KB | Configuracao/Contrato em formato JSON. |
| models.txt | Projeto | Texto/Binario | 1 | 1.9 KB | Projeto em formato Texto/Binario. |
| models/piper/pt_BR_maria_low.onnx | Binario/artefato | ONNX |  | 29 B | Binario/artefato em formato ONNX. |
| models/piper/pt_BR_maria_low.onnx.json | Configuracao/Contrato | JSON | 1 | 29 B | Configuracao/Contrato em formato JSON. |
| nexus-iced/Cargo.lock | Projeto | Lockfile | 5330 | 131.4 KB | Lockfile Cargo com dependencias Rust resolvidas. |
| nexus-iced/Cargo.toml | Configuracao/Contrato | TOML | 17 | 460 B | Manifesto Cargo do crate/workspace Rust. |
| nexus-iced/src/main.rs | Codigo Rust | Rust | 8668 | 293.4 KB | GUI Rust/Iced principal. |
| nexus-iced/src/websocket.rs | Codigo Rust | Rust | 155 | 3.8 KB | Cliente/eventos WebSocket da GUI. |
| nexus_core/__init__.py | Codigo Python | Python | 5 | 79 B | Inicializador de pacote Python. |
| nexus_core/actions.py | Codigo Python | Python | 514 | 18.8 KB | Modulo Python `actions`. |
| nexus_core/actions_registry.py | Codigo Python | Python | 38 | 947 B | Modulo Python `actions registry`. |
| nexus_core/agent.py | Codigo Python | Python | 1148 | 37.3 KB | Modulo Python `agent`. |
| nexus_core/architect_agent.py | Codigo Python | Python | 107 | 4.3 KB | Modulo Python `architect agent`. |
| nexus_core/asr.py | Codigo Python | Python | 113 | 3.3 KB | Modulo Python `asr`. |
| nexus_core/boot_diagnostics.py | Codigo Python | Python | 51 | 1.8 KB | Modulo Python `boot diagnostics`. |
| nexus_core/browser_control.py | Codigo Python | Python | 165 | 5.4 KB | Modulo Python `browser control`. |
| nexus_core/cognitive/__init__.py | Codigo Python | Python | 13 | 300 B | Inicializador de pacote Python. |
| nexus_core/cognitive/__main__.py | Codigo Python | Python | 5 | 123 B | Modulo Python `  main  `. |
| nexus_core/cognitive/attention_engine.py | Codigo Python | Python | 249 | 8.3 KB | Modulo Python `attention engine`. |
| nexus_core/cognitive/classifier.py | Codigo Python | Python | 67 | 2.0 KB | Modulo Python `classifier`. |
| nexus_core/cognitive/cognition_service.py | Codigo Python | Python | 131 | 4.0 KB | Modulo Python `cognition service`. |
| nexus_core/cognitive/cognitive_db.py | Codigo Python | Python | 255 | 8.9 KB | Modulo Python `cognitive db`. |
| nexus_core/cognitive/cognitive_loop.py | Codigo Python | Python | 715 | 27.2 KB | Modulo Python `cognitive loop`. |
| nexus_core/cognitive/cognitive_state.py | Codigo Python | Python | 126 | 4.0 KB | Modulo Python `cognitive state`. |
| nexus_core/cognitive/context_engine.py | Codigo Python | Python | 89 | 2.8 KB | Modulo Python `context engine`. |
| nexus_core/cognitive/execution_engine.py | Codigo Python | Python | 325 | 10.7 KB | Modulo Python `execution engine`. |
| nexus_core/cognitive/goal_engine.py | Codigo Python | Python | 277 | 9.0 KB | Modulo Python `goal engine`. |
| nexus_core/cognitive/learning_engine.py | Codigo Python | Python | 259 | 8.1 KB | Modulo Python `learning engine`. |
| nexus_core/cognitive/memory_compression.py | Codigo Python | Python | 173 | 6.3 KB | Modulo Python `memory compression`. |
| nexus_core/cognitive/planner.py | Codigo Python | Python | 326 | 10.0 KB | Modulo Python `planner`. |
| nexus_core/cognitive/predictive_engine.py | Codigo Python | Python | 113 | 3.9 KB | Modulo Python `predictive engine`. |
| nexus_core/cognitive/priority_orchestrator.py | Codigo Python | Python | 165 | 5.4 KB | Modulo Python `priority orchestrator`. |
| nexus_core/cognitive/reflection_engine.py | Codigo Python | Python | 357 | 12.0 KB | Modulo Python `reflection engine`. |
| nexus_core/cognitive/self_healing.py | Codigo Python | Python | 116 | 3.8 KB | Modulo Python `self healing`. |
| nexus_core/cognitive/simulator.py | Codigo Python | Python | 217 | 7.8 KB | Modulo Python `simulator`. |
| nexus_core/cognitive/user_profile_engine.py | Codigo Python | Python | 764 | 26.5 KB | Modulo Python `user profile engine`. |
| nexus_core/command_policy.py | Codigo Python | Python | 295 | 7.0 KB | Modulo Python `command policy`. |
| nexus_core/config_guard.py | Codigo Python | Python | 138 | 4.8 KB | Modulo Python `config guard`. |
| nexus_core/conversation/context_builder.py | Codigo Python | Python | 94 | 3.2 KB | Modulo Python `context builder`. |
| nexus_core/conversation/conversation_manager.py | Codigo Python | Python | 59 | 2.0 KB | Modulo Python `conversation manager`. |
| nexus_core/conversation/response_sanitizer.py | Codigo Python | Python | 58 | 1.8 KB | Modulo Python `response sanitizer`. |
| nexus_core/conversation/sqlite_conversation_memory.py | Codigo Python | Python | 183 | 5.3 KB | Modulo Python `sqlite conversation memory`. |
| nexus_core/conversation/topic_tracker.py | Codigo Python | Python | 58 | 2.2 KB | Modulo Python `topic tracker`. |
| nexus_core/conversation/turn_store.py | Codigo Python | Python | 86 | 2.7 KB | Modulo Python `turn store`. |
| nexus_core/core_system.py | Codigo Python | Python | 771 | 26.7 KB | Modulo Python `core system`. |
| nexus_core/diagnostics.py | Codigo Python | Python | 79 | 2.2 KB | Modulo Python `diagnostics`. |
| nexus_core/env.py | Codigo Python | Python | 23 | 684 B | Modulo Python `env`. |
| nexus_core/event_pipeline.py | Codigo Python | Python | 107 | 3.2 KB | Modulo Python `event pipeline`. |
| nexus_core/events/event_bus.py | Codigo Python | Python | 232 | 7.0 KB | Modulo Python `event bus`. |
| nexus_core/events/sync_engine.py | Codigo Python | Python | 355 | 12.2 KB | Modulo Python `sync engine`. |
| nexus_core/events/sync_worker.py | Codigo Python | Python | 78 | 2.8 KB | Modulo Python `sync worker`. |
| nexus_core/events/watcher.py | Codigo Python | Python | 77 | 2.7 KB | Modulo Python `watcher`. |
| nexus_core/execution_engine.py | Codigo Python | Python | 125 | 4.2 KB | Modulo Python `execution engine`. |
| nexus_core/execution_protocol.py | Codigo Python | Python | 810 | 26.1 KB | Ledger e protocolo evidence-first para execucao real de comandos. |
| nexus_core/executive_agent.py | Codigo Python | Python | 101 | 3.5 KB | Modulo Python `executive agent`. |
| nexus_core/executor.py | Codigo Python | Python | 129 | 4.2 KB | Modulo Python `executor`. |
| nexus_core/health_status.py | Codigo Python | Python | 138 | 4.0 KB | Modulo Python `health status`. |
| nexus_core/integrations/filesystem_mirror.py | Codigo Python | Python | 190 | 7.0 KB | Modulo Python `filesystem mirror`. |
| nexus_core/integrations/linear.py | Codigo Python | Python | 207 | 5.6 KB | Modulo Python `linear`. |
| nexus_core/integrations/notion.py | Codigo Python | Python | 232 | 7.6 KB | Modulo Python `notion`. |
| nexus_core/integrations/obsidian.py | Codigo Python | Python | 123 | 4.0 KB | Modulo Python `obsidian`. |
| nexus_core/interaction/interaction_engine.py | Codigo Python | Python | 68 | 2.7 KB | Modulo Python `interaction engine`. |
| nexus_core/learning_engine.py | Codigo Python | Python | 112 | 4.0 KB | Modulo Python `learning engine`. |
| nexus_core/llm_service.py | Codigo Python | Python | 63 | 1.9 KB | Modulo Python `llm service`. |
| nexus_core/long_term_memory.py | Codigo Python | Python | 191 | 5.8 KB | Modulo Python `long term memory`. |
| nexus_core/memory/context_manager.py | Codigo Python | Python | 57 | 1.9 KB | Modulo Python `context manager`. |
| nexus_core/memory/sqlite_memory.py | Codigo Python | Python | 272 | 7.8 KB | Modulo Python `sqlite memory`. |
| nexus_core/memory_hierarchy.py | Codigo Python | Python | 96 | 3.6 KB | Modulo Python `memory hierarchy`. |
| nexus_core/memory_manager.py | Codigo Python | Python | 427 | 14.3 KB | Modulo Python `memory manager`. |
| nexus_core/model_router.py | Codigo Python | Python | 102 | 2.6 KB | Roteamento local/cloud por complexidade e risco. |
| nexus_core/models/__init__.py | Codigo Python | Python | 3 | 143 B | Inicializador de pacote Python. |
| nexus_core/models/base_model_client.py | Codigo Python | Python | 21 | 414 B | Modulo Python `base model client`. |
| nexus_core/models/cloud_client.py | Codigo Python | Python | 42 | 1.1 KB | Modulo Python `cloud client`. |
| nexus_core/models/model_registry.py | Codigo Python | Python | 23 | 740 B | Modulo Python `model registry`. |
| nexus_core/models/ollama_client.py | Codigo Python | Python | 184 | 5.4 KB | Modulo Python `ollama client`. |
| nexus_core/nexus_core_v3.py | Codigo Python | Python | 189 | 6.2 KB | Modulo Python `nexus core v3`. |
| nexus_core/observability.py | Codigo Python | Python | 111 | 3.4 KB | Modulo Python `observability`. |
| nexus_core/organization/__init__.py | Codigo Python | Python | 50 | 1.8 KB | Inicializador de pacote Python. |
| nexus_core/organization/__main__.py | Codigo Python | Python | 358 | 12.9 KB | Modulo Python `  main  `. |
| nexus_core/organization/agents.py | Codigo Python | Python | 248 | 7.7 KB | Modulo Python `agents`. |
| nexus_core/organization/blackboard.py | Codigo Python | Python | 259 | 8.1 KB | Modulo Python `blackboard`. |
| nexus_core/organization/config.py | Codigo Python | Python | 164 | 5.2 KB | Modulo Python `config`. |
| nexus_core/organization/continuous.py | Codigo Python | Python | 100 | 3.3 KB | Modulo Python `continuous`. |
| nexus_core/organization/daemon.py | Codigo Python | Python | 267 | 9.3 KB | Daemon persistente que integra memoria, blackboard, permissoes, swarm, runtime e workspace context. |
| nexus_core/organization/execution_plans.py | Codigo Python | Python | 160 | 5.1 KB | Plano estruturado de execucao e etapas auditaveis. |
| nexus_core/organization/health.py | Codigo Python | Python | 263 | 7.5 KB | Modulo Python `health`. |
| nexus_core/organization/memory.py | Codigo Python | Python | 1440 | 52.2 KB | SQLite organizacional para tarefas, decisoes, eventos, comandos, verificacoes, planos e replays. |
| nexus_core/organization/observer.py | Codigo Python | Python | 195 | 6.5 KB | Modulo Python `observer`. |
| nexus_core/organization/replay.py | Codigo Python | Python | 169 | 6.3 KB | Reconstrucao de timeline de comando ou tarefa. |
| nexus_core/organization/resource_budget.py | Codigo Python | Python | 124 | 4.1 KB | Orcamento de CPU/RAM/timeout/concorrencia/tokens para autonomia segura. |
| nexus_core/organization/runtime.py | Codigo Python | Python | 403 | 14.6 KB | Runtime de execucao verificavel com planos, budgets, evidencia, replay e self-healing. |
| nexus_core/organization/security.py | Codigo Python | Python | 345 | 11.6 KB | Politica, fila de aprovacao e fronteira entre proposta/aprovacao/execucao. |
| nexus_core/organization/self_healing.py | Codigo Python | Python | 144 | 5.2 KB | Diagnostico de falhas e passos de recuperacao seguros. |
| nexus_core/organization/swarm.py | Codigo Python | Python | 334 | 11.8 KB | Modulo Python `swarm`. |
| nexus_core/organization/verification.py | Codigo Python | Python | 140 | 4.8 KB | Modulo Python `verification`. |
| nexus_core/organization/workspace_context.py | Codigo Python | Python | 205 | 6.6 KB | Detector de traits do workspace. |
| nexus_core/path_filters.py | Codigo Python | Python | 66 | 1.2 KB | Modulo Python `path filters`. |
| nexus_core/peripherals/bluetooth_monitor.py | Codigo Python | Python | 95 | 3.2 KB | Modulo Python `bluetooth monitor`. |
| nexus_core/peripherals/usb_monitor.py | Codigo Python | Python | 323 | 11.5 KB | Modulo Python `usb monitor`. |
| nexus_core/planner.py | Codigo Python | Python | 121 | 3.5 KB | Modulo Python `planner`. |
| nexus_core/product_cli.py | Codigo Python | Python | 484 | 15.9 KB | CLI de produto Linux para status, modelos e roteamento. |
| nexus_core/recovery_engine.py | Codigo Python | Python | 87 | 3.1 KB | Modulo Python `recovery engine`. |
| nexus_core/resource_control.py | Codigo Python | Python | 90 | 3.2 KB | Modulo Python `resource control`. |
| nexus_core/response_text.py | Codigo Python | Python | 218 | 6.5 KB | Modulo Python `response text`. |
| nexus_core/runtime/resource_governor.py | Codigo Python | Python | 95 | 3.3 KB | Modulo Python `resource governor`. |
| nexus_core/rust_sensors.py | Codigo Python | Python | 73 | 2.1 KB | Modulo Python `rust sensors`. |
| nexus_core/security/daemon_client.py | Codigo Python | Python | 143 | 4.6 KB | Modulo Python `daemon client`. |
| nexus_core/security/privacy_guard.py | Codigo Python | Python | 322 | 10.9 KB | Modulo Python `privacy guard`. |
| nexus_core/security/root_daemon.py | Codigo Python | Python | 855 | 28.3 KB | Modulo Python `root daemon`. |
| nexus_core/security_guard.py | Codigo Python | Python | 143 | 3.8 KB | Modulo Python `security guard`. |
| nexus_core/self_improvement/audit_log.py | Codigo Python | Python | 67 | 1.9 KB | Modulo Python `audit log`. |
| nexus_core/self_improvement/patch_manager.py | Codigo Python | Python | 55 | 1.8 KB | Modulo Python `patch manager`. |
| nexus_core/self_improvement/pipeline.py | Codigo Python | Python | 135 | 5.0 KB | Modulo Python `pipeline`. |
| nexus_core/self_improvement/rollback_manager.py | Codigo Python | Python | 36 | 1.2 KB | Modulo Python `rollback manager`. |
| nexus_core/sentry_observability.py | Codigo Python | Python | 101 | 2.8 KB | Modulo Python `sentry observability`. |
| nexus_core/simulation_layer.py | Codigo Python | Python | 111 | 3.7 KB | Modulo Python `simulation layer`. |
| nexus_core/skill_engine.py | Codigo Python | Python | 51 | 1.9 KB | Modulo Python `skill engine`. |
| nexus_core/synaptic_sync.py | Codigo Python | Python | 68 | 2.7 KB | Modulo Python `synaptic sync`. |
| nexus_core/tools.py | Codigo Python | Python | 178 | 5.8 KB | Modulo Python `tools`. |
| nexus_core/v4/__init__.py | Codigo Python | Python | 1 | 49 B | Inicializador de pacote Python. |
| nexus_core/v4/core.py | Codigo Python | Python | 230 | 7.5 KB | Modulo Python `core`. |
| nexus_core/v4/executor.py | Codigo Python | Python | 259 | 8.3 KB | Modulo Python `executor`. |
| nexus_core/v4/goals.py | Codigo Python | Python | 122 | 3.7 KB | Modulo Python `goals`. |
| nexus_core/v4/guardian.py | Codigo Python | Python | 109 | 3.8 KB | Modulo Python `guardian`. |
| nexus_core/v4/memory.py | Codigo Python | Python | 87 | 2.7 KB | Modulo Python `memory`. |
| nexus_core/v4/planner.py | Codigo Python | Python | 149 | 4.9 KB | Modulo Python `planner`. |
| nexus_core/v4/reward.py | Codigo Python | Python | 35 | 917 B | Modulo Python `reward`. |
| nexus_core/v4/sensors.py | Codigo Python | Python | 181 | 5.7 KB | Modulo Python `sensors`. |
| nexus_core/v4/types.py | Codigo Python | Python | 91 | 1.8 KB | Modulo Python `types`. |
| nexus_core/vector_memory.py | Codigo Python | Python | 195 | 6.4 KB | Modulo Python `vector memory`. |
| nexus_core/vision.py | Codigo Python | Python | 177 | 5.5 KB | Modulo Python `vision`. |
| nexus_core/voice_sensing.py | Codigo Python | Python | 568 | 20.9 KB | Modulo Python `voice sensing`. |
| packaging/debian/changelog | Empacotamento | Texto/Binario | 40 | 1.4 KB | Empacotamento em formato Texto/Binario. |
| packaging/debian/conffiles | Empacotamento | Texto/Binario | 2 | 44 B | Empacotamento em formato Texto/Binario. |
| packaging/debian/control | Empacotamento | Texto/Binario | 12 | 485 B | Empacotamento em formato Texto/Binario. |
| packaging/debian/copyright | Empacotamento | Texto/Binario | 7 | 243 B | Empacotamento em formato Texto/Binario. |
| packaging/debian/postinst | Empacotamento | Texto/Binario | 37 | 831 B | Empacotamento em formato Texto/Binario. |
| packaging/debian/postrm | Empacotamento | Texto/Binario | 8 | 109 B | Empacotamento em formato Texto/Binario. |
| packaging/debian/prerm | Empacotamento | Texto/Binario | 8 | 130 B | Empacotamento em formato Texto/Binario. |
| packaging/debian/rules | Empacotamento | Texto/Binario | 4 | 30 B | Empacotamento em formato Texto/Binario. |
| packaging/desktop/nexus.desktop | Empacotamento | Texto/Binario | 7 | 157 B | Empacotamento em formato Texto/Binario. |
| packaging/scripts/build_deb.sh | Empacotamento | Shell | 49 | 1.8 KB | Build deterministico do pacote Debian. |
| packaging/scripts/nexus-health | Empacotamento | Texto/Binario | 3 | 61 B | Empacotamento em formato Texto/Binario. |
| packaging/scripts/nexus-setup | Empacotamento | Texto/Binario | 3 | 60 B | Empacotamento em formato Texto/Binario. |
| packaging/scripts/nexus-uninstall | Empacotamento | Texto/Binario | 3 | 64 B | Empacotamento em formato Texto/Binario. |
| packaging/systemd/nexus.service | Empacotamento | systemd | 30 | 814 B | Unidade systemd para daemonizacao. |
| pattern_engine.py | Codigo Python | Python | 98 | 3.1 KB | Modulo Python `pattern engine`. |
| pyproject.toml | Configuracao/Contrato | TOML | 15 | 299 B | Configuracao de lint, formatacao e type checking Python. |
| pytest.ini | Projeto | Texto/Binario | 10 | 342 B | Configuracao global do pytest. |
| requirements/ai.txt | Projeto | Texto/Binario | 7 | 148 B | Dependencias Python do perfil ai. |
| requirements/base.txt | Projeto | Texto/Binario | 13 | 321 B | Dependencias Python do perfil base. |
| requirements/browser.txt | Projeto | Texto/Binario | 1 | 22 B | Dependencias Python do perfil browser. |
| requirements/dev.txt | Projeto | Texto/Binario | 8 | 125 B | Dependencias Python do perfil dev. |
| requirements/voice.txt | Projeto | Texto/Binario | 9 | 192 B | Dependencias Python do perfil voice. |
| scripts/bootstrap.sh | Script/automacao | Shell | 20 | 609 B | Script/automacao em formato Shell. |
| scripts/dev-check.sh | Script/automacao | Shell | 23 | 687 B | Script/automacao em formato Shell. |
| scripts/mirror_os_to_obsidian.py | Codigo Python | Python | 591 | 19.4 KB | Modulo Python `mirror os to obsidian`. |
| scripts/nexus.service | Configuracao/Contrato | systemd | 16 | 428 B | Unidade systemd para daemonizacao. |
| skills/system_guardian.py | Codigo Python | Python | 33 | 1.2 KB | Modulo Python `system guardian`. |
| test_db/45021409-9b31-44c1-b211-877bee7c6e64/data_level0.bin | Binario/artefato | Binary |  | 14.8 KB | Binario/artefato em formato Binary. |
| test_db/45021409-9b31-44c1-b211-877bee7c6e64/header.bin | Binario/artefato | Binary |  | 100 B | Binario/artefato em formato Binary. |
| test_db/45021409-9b31-44c1-b211-877bee7c6e64/length.bin | Binario/artefato | Binary |  | 400 B | Binario/artefato em formato Binary. |
| test_db/45021409-9b31-44c1-b211-877bee7c6e64/link_lists.bin | Binario/artefato | Binary |  | 0 B | Binario/artefato em formato Binary. |
| test_db/chroma.sqlite3 | Projeto | Texto/Binario |  | 184.0 KB | Projeto em formato Texto/Binario. |
| tests/conftest.py | Teste | Python | 43 | 1.6 KB | Teste conftest para validar comportamento do sistema. |
| tests/integration/test_backend_regressions.py | Teste | Python | 249 | 9.3 KB | Teste test backend regressions para validar comportamento do sistema. |
| tests/integration/test_cognition_routes.py | Teste | Python | 79 | 2.6 KB | Teste test cognition routes para validar comportamento do sistema. |
| tests/integration/test_filesystem_mirror.py | Teste | Python | 59 | 1.8 KB | Teste test filesystem mirror para validar comportamento do sistema. |
| tests/integration/test_second_brain.py | Teste | Python | 119 | 4.3 KB | Teste test second brain para validar comportamento do sistema. |
| tests/integration/test_status_routes.py | Teste | Python | 131 | 4.7 KB | Teste test status routes para validar comportamento do sistema. |
| tests/system/test_cognitive_loop.py | Teste | Python | 87 | 3.3 KB | Teste test cognitive loop para validar comportamento do sistema. |
| tests/system/test_root_daemon.py | Teste | Python | 81 | 2.4 KB | Teste test root daemon para validar comportamento do sistema. |
| tests/system/test_rust_sensors.py | Teste | Python | 25 | 838 B | Teste test rust sensors para validar comportamento do sistema. |
| tests/unit/test_agent_feedback.py | Teste | Python | 123 | 3.9 KB | Teste test agent feedback para validar comportamento do sistema. |
| tests/unit/test_attention_engine.py | Teste | Python | 60 | 2.2 KB | Teste test attention engine para validar comportamento do sistema. |
| tests/unit/test_cognitive_db.py | Teste | Python | 74 | 2.6 KB | Teste test cognitive db para validar comportamento do sistema. |
| tests/unit/test_cognitive_execution.py | Teste | Python | 151 | 5.0 KB | Teste test cognitive execution para validar comportamento do sistema. |
| tests/unit/test_cognitive_learning.py | Teste | Python | 118 | 4.2 KB | Teste test cognitive learning para validar comportamento do sistema. |
| tests/unit/test_cognitive_maturity_final.py | Teste | Python | 45 | 1.9 KB | Teste test cognitive maturity final para validar comportamento do sistema. |
| tests/unit/test_cognitive_planner.py | Teste | Python | 92 | 3.0 KB | Teste test cognitive planner para validar comportamento do sistema. |
| tests/unit/test_cognitive_simulator.py | Teste | Python | 161 | 5.7 KB | Teste test cognitive simulator para validar comportamento do sistema. |
| tests/unit/test_cognitive_state.py | Teste | Python | 80 | 2.5 KB | Teste test cognitive state para validar comportamento do sistema. |
| tests/unit/test_command_policy.py | Teste | Python | 204 | 8.1 KB | Teste test command policy para validar comportamento do sistema. |
| tests/unit/test_config_guard.py | Teste | Python | 98 | 3.3 KB | Teste test config guard para validar comportamento do sistema. |
| tests/unit/test_conversation_memory.py | Teste | Python | 22 | 861 B | Teste test conversation memory para validar comportamento do sistema. |
| tests/unit/test_event_pipeline.py | Teste | Python | 29 | 851 B | Teste test event pipeline para validar comportamento do sistema. |
| tests/unit/test_execution_protocol.py | Teste | Python | 270 | 9.8 KB | Teste test execution protocol para validar comportamento do sistema. |
| tests/unit/test_goal_engine.py | Teste | Python | 107 | 3.7 KB | Teste test goal engine para validar comportamento do sistema. |
| tests/unit/test_llm_service.py | Teste | Python | 34 | 1.0 KB | Teste test llm service para validar comportamento do sistema. |
| tests/unit/test_memory_compression.py | Teste | Python | 73 | 3.0 KB | Teste test memory compression para validar comportamento do sistema. |
| tests/unit/test_model_router.py | Teste | Python | 37 | 1.1 KB | Teste test model router para validar comportamento do sistema. |
| tests/unit/test_observability.py | Teste | Python | 73 | 2.1 KB | Teste test observability para validar comportamento do sistema. |
| tests/unit/test_ollama_client.py | Teste | Python | 30 | 913 B | Teste test ollama client para validar comportamento do sistema. |
| tests/unit/test_organization_daemon.py | Teste | Python | 69 | 2.4 KB | Teste test organization daemon para validar comportamento do sistema. |
| tests/unit/test_organization_health.py | Teste | Python | 152 | 4.5 KB | Teste test organization health para validar comportamento do sistema. |
| tests/unit/test_organization_memory.py | Teste | Python | 171 | 5.7 KB | Teste test organization memory para validar comportamento do sistema. |
| tests/unit/test_organization_observer.py | Teste | Python | 150 | 5.1 KB | Teste test organization observer para validar comportamento do sistema. |
| tests/unit/test_organization_runtime.py | Teste | Python | 132 | 5.1 KB | Teste test organization runtime para validar comportamento do sistema. |
| tests/unit/test_organization_security.py | Teste | Python | 93 | 3.4 KB | Teste test organization security para validar comportamento do sistema. |
| tests/unit/test_path_filters.py | Teste | Python | 37 | 1.1 KB | Teste test path filters para validar comportamento do sistema. |
| tests/unit/test_privacy_guard.py | Teste | Python | 96 | 3.3 KB | Teste test privacy guard para validar comportamento do sistema. |
| tests/unit/test_realtime_hub.py | Teste | Python | 64 | 1.7 KB | Teste test realtime hub para validar comportamento do sistema. |
| tests/unit/test_reflection_engine.py | Teste | Python | 99 | 3.3 KB | Teste test reflection engine para validar comportamento do sistema. |
| tests/unit/test_resource_budget.py | Teste | Python | 26 | 800 B | Teste test resource budget para validar comportamento do sistema. |
| tests/unit/test_response_text.py | Teste | Python | 40 | 1.3 KB | Teste test response text para validar comportamento do sistema. |
| tests/unit/test_response_text_voice.py | Teste | Python | 26 | 767 B | Teste test response text voice para validar comportamento do sistema. |
| tests/unit/test_security_guard.py | Teste | Python | 81 | 2.8 KB | Teste test security guard para validar comportamento do sistema. |
| tests/unit/test_self_healing.py | Teste | Python | 25 | 704 B | Teste test self healing para validar comportamento do sistema. |
| tests/unit/test_swarm_orchestrator.py | Teste | Python | 52 | 1.6 KB | Teste test swarm orchestrator para validar comportamento do sistema. |
| tests/unit/test_temporal_context.py | Teste | Python | 26 | 774 B | Teste test temporal context para validar comportamento do sistema. |
| tests/unit/test_usb_monitor.py | Teste | Python | 93 | 2.6 KB | Teste test usb monitor para validar comportamento do sistema. |
| tests/unit/test_user_profile_engine.py | Teste | Python | 113 | 4.1 KB | Teste test user profile engine para validar comportamento do sistema. |
| tests/unit/test_workspace_context.py | Teste | Python | 38 | 1.5 KB | Teste test workspace context para validar comportamento do sistema. |
| tools/cleanup_workspace.sh | Script/automacao | Shell | 21 | 557 B | Script/automacao em formato Shell. |
| tools/migrate_synaptic_memory_paths.py | Codigo Python | Python | 82 | 2.4 KB | Modulo Python `migrate synaptic memory paths`. |
| ui/static/app.js | Projeto | Texto/Binario | 60 | 1.8 KB | Projeto em formato Texto/Binario. |
| ui/static/index.html | Projeto | Texto/Binario | 193 | 6.9 KB | Projeto em formato Texto/Binario. |
| ui/static/styles.css | Projeto | Texto/Binario | 12 | 1.2 KB | Projeto em formato Texto/Binario. |
| watcher_rs/.gitignore | Projeto | Texto/Binario | 1 | 8 B | Projeto em formato Texto/Binario. |
| watcher_rs/Cargo.lock | Projeto | Lockfile | 1279 | 32.2 KB | Lockfile Cargo com dependencias Rust resolvidas. |
| watcher_rs/Cargo.toml | Configuracao/Contrato | TOML | 16 | 385 B | Manifesto Cargo do crate/workspace Rust. |
| watcher_rs/src/main.rs | Codigo Rust | Rust | 248 | 7.0 KB | Modulo Rust `main`. |

## 7. Observacoes finais

- Pastas como `.git`, `.venv`, `target`, caches locais e logs nao entram no inventario rastreado pelo Git.
- `dist/` esta rastreado e foi incluido como artefato gerado/empacotamento para mostrar a entrega Debian atual.
- O fluxo de maior criticidade e `aprovacao -> plano -> budget -> execucao -> verificacao -> replay -> memoria`.
- A interface principal deve continuar escondendo complexidade tecnica, enquanto o runtime preserva rastreabilidade completa.
