# Plano de Execucao do ZEUS_SYSTEM

Data: 2026-05-02  
Objetivo: reduzir risco, melhorar confiabilidade e preparar o sistema para evolucao sem aumentar o acoplamento.

## Ordem de execucao

### 1. Blindagem de configuracao

Meta: impedir que o sistema suba com segredos fracos, modo inseguro ou cloud mal configurado.

Status: iniciado em 2026-05-02. Validacao central criada em `zeus_core/config_guard.py`.

Tarefas:

1. Concluido: validar `ZEUS_JWT_SECRET` forte por ambiente.
2. Concluido: exigir `ZEUS_LAN_TOKEN` quando `ZEUS_ALLOW_LAN=1` ou bind remoto estiver ativo.
3. Concluido: validar `ZEUS_LLM_PROVIDER` e credenciais obrigatorias por provider.
4. Concluido: falhar boot em `prod` quando houver fallback inseguro de JWT.
5. Concluido: expor diagnostico de configuracao na UI sem vazar segredo.
6. Concluido: criar perfil formal `local`, `lan` e `prod` documentado.

Critério de pronto:

- o sistema recusa configuração inválida;
- a UI mostra o estado correto;
- o teste de LLM retorna erro claro quando faltar auth.

### 2. Modularização do backend

Meta: reduzir o tamanho e o risco de `apps/web_gui.py`.

Status: concluido em 2026-05-02. Seguranca/rede, rotas de status, realtime, pipeline do watcher e servico LLM extraidos.

Tarefas:

1. Concluido: extrair segurança para um módulo dedicado.
2. Concluido: extrair endpoints de saúde e status.
3. Concluido: extrair WebSocket/Socket.IO para uma camada própria.
4. Concluido: extrair pipeline de eventos do watcher.
5. Concluido: separar integração de LLM do resto da API.

Critério de pronto:

- o comportamento externo continua igual;
- os módulos ficam testáveis isoladamente;
- `apps/web_gui.py` deixa de concentrar tudo.

### 3. Testes de integração

Meta: cobrir os fluxos que mais quebram.

Status: iniciado em 2026-05-02. Rotas operacionais, seguranca realtime e politica de comandos cobertas por testes de contrato.

Tarefas:

1. Concluido: testar auth local e LAN em `security_guard`.
2. Concluido: testar `/api/health` via router extraido.
3. Concluido: testar `/api/llm/status` e `/api/llm/test` via router extraido.
4. Concluido: testar rejeicao realtime sem credencial via guards e hub.
5. Concluido: testar allowlist de comandos.
6. Pendente: adicionar smoke real com servidor quando `httpx`/`TestClient` estiver disponivel.

Critério de pronto:

- falhas críticas passam a ser detectadas automaticamente;
- o conjunto de testes evita regressão nos pontos principais.

### 4. Observabilidade

Meta: facilitar diagnóstico sem depender da interface.

Status: iniciado em 2026-05-02. Logs estruturados, correlation-id e metricas minimas adicionados.

Tarefas:

1. Concluido: adotar logs estruturados.
2. Concluido: adicionar correlation-id por request.
3. Concluido: expor métricas mínimas por módulo.
4. Concluido: separar warning operacional de erro real nos fluxos novos.
5. Concluido: registrar falhas de provider LLM com contexto suficiente.
6. Pendente: migrar prints legados gradualmente para logger estruturado.

Critério de pronto:

- fica fácil saber o que falhou, onde e quando;
- os logs deixam de ser apenas texto solto.

### 5. Política de comandos

Meta: reduzir o risco de execução indevida.

Status: concluido em 2026-05-02. `cmd_control` agora usa politica central com classificacao, confirmacao e auditoria.

Tarefas:

1. Concluido: separar comandos de leitura e escrita.
2. Concluido: requerer confirmação para operações de escrita.
3. Concluido: bloquear encadeamentos perigosos.
4. Concluido: registrar auditoria das ações sensíveis.

Critério de pronto:

- comandos perigosos não executam por acidente;
- a política é previsível e auditável.

### 6. UX e operação

Meta: tornar o sistema mais fácil de entender e operar.

Tarefas:

1. Simplificar o painel web.
2. Reduzir ruído visual de debug.
3. Melhorar mensagens de erro no front.
4. Unificar estados entre web e overlay.
5. Melhorar onboarding para cloud/local.

Critério de pronto:

- o estado do sistema fica claro em poucos segundos;
- o usuário não precisa adivinhar o que está quebrado.

## Entregas sugeridas

### Curto prazo

1. `security_guard.py`
2. `health_routes.py`
3. `realtime_hub.py`
4. `event_pipeline.py`
5. `tests/test_auth_and_health.py`

### Medio prazo

1. `llm_provider.py`
2. `command_policy.py`
3. `tests/test_realtime_security.py`
4. `tests/test_command_policy.py`

### Longo prazo

1. `observability.py`
2. `metrics_exporter.py`
3. `ops_dashboard`
4. `smoke_test_runner`

## Sequencia recomendada

1. Fechar configuracao e segredos.
2. Quebrar o backend em módulos.
3. Cobrir auth, health e realtime com testes.
4. Melhorar observabilidade.
5. Endurecer comandos.
6. Refinar UX.

## Resultado esperado

Ao final dessa ordem, o sistema deve ficar:

- mais previsível;
- mais seguro;
- mais fácil de testar;
- mais fácil de manter;
- mais pronto para evoluir sem quebrar fluxos existentes.
