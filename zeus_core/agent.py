import asyncio
import datetime as _dt
import json
import os
from typing import Awaitable, Callable, Dict, Optional, Tuple

from zeus_core.core_system import call_cloud_llm, call_cloud_llm_stream
from zeus_core.executor import PlanExecutor
from zeus_core.tools import ToolError
from zeus_core.actions import get_actions
from zeus_core.security.privacy_guard import PrivacyGuard

privacy_guard = PrivacyGuard()


BroadcastFn = Callable[[dict], Awaitable[None]]


_TOOL_TAG_OPEN = "<tool_call>"
_TOOL_TAG_CLOSE = "</tool_call>"


_PENDING_CONFIRMATIONS: Dict[str, dict] = {}


def _tool_mode() -> str:
    # confirm: pede "Sim" antes de executar execute_bash
    # auto: executa sem confirmação
    mode = os.getenv("ZEUS_TOOL_EXECUTION_MODE", "confirm").strip().lower()
    return mode if mode in {"confirm", "auto"} else "confirm"


def _extract_tool_call(text: str) -> Tuple[Optional[dict], str]:
    if not isinstance(text, str):
        return None, ""

    start = text.find(_TOOL_TAG_OPEN)
    if start == -1:
        return None, text
    end = text.find(_TOOL_TAG_CLOSE, start)
    if end == -1:
        return None, text

    before = text[:start].strip()
    inside = text[start + len(_TOOL_TAG_OPEN) : end].strip()
    after = text[end + len(_TOOL_TAG_CLOSE) :].strip()

    payload_str = inside
    payload = None
    try:
        payload = json.loads(payload_str)
    except Exception:
        # Fallback: tenta recortar do primeiro "{" ao último "}".
        left = payload_str.find("{")
        right = payload_str.rfind("}")
        if left != -1 and right != -1 and right > left:
            try:
                payload = json.loads(payload_str[left : right + 1])
            except Exception:
                payload = None

    remaining = "\n".join([p for p in [before, after] if p])
    return payload, remaining


def _is_confirmation_message(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {"sim", "s", "confirmo", "confirmar", "ok"}


def _progress_enabled() -> bool:
    value = os.getenv("ZEUS_AGENT_PROGRESS_EVENTS", "1").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _summarize_tool_result(result: dict) -> dict:
    if not isinstance(result, dict):
        return {"ok": True, "summary": str(result)[:500]}

    summary = {
        "ok": bool(result.get("ok", result.get("status") not in {"error", "failed"})),
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "category": result.get("category"),
        "requires_confirmation": result.get("requires_confirmation"),
        "error": result.get("error"),
    }
    stdout = result.get("stdout")
    stderr = result.get("stderr")
    if isinstance(stdout, str) and stdout.strip():
        summary["stdout_preview"] = stdout.strip()[:800]
    if isinstance(stderr, str) and stderr.strip():
        summary["stderr_preview"] = stderr.strip()[:800]
    if "message" in result:
        summary["message"] = str(result.get("message"))[:800]
    return {k: v for k, v in summary.items() if v is not None}


class Agent:
    def __init__(self, *, max_steps: int = 6):
        self.max_steps = max_steps
        self._actions = get_actions()
        self._plan_executor = PlanExecutor()

    def _get_dynamic_max_steps(self, user_prompt: str) -> int:
        prompt_lower = user_prompt.lower()
        if (
            "melhorar zeus" in prompt_lower
            or "refatorar si mesmo" in prompt_lower
            or "patch" in prompt_lower
        ):
            return int(os.getenv("ZEUS_MAX_STEPS_SELF_IMPROVEMENT", "18"))
        if (
            "sudo" in prompt_lower
            or "root" in prompt_lower
            or "apt install" in prompt_lower
        ):
            return int(os.getenv("ZEUS_MAX_STEPS_ADMIN", "14"))
        if (
            "arquitetura" in prompt_lower
            or "design" in prompt_lower
            or "planejar" in prompt_lower
        ):
            return int(os.getenv("ZEUS_MAX_STEPS_COMPLEX", "12"))
        if "erro crítico" in prompt_lower or "falha grave" in prompt_lower:
            return int(os.getenv("ZEUS_MAX_STEPS_CRITICAL", "16"))
        return int(os.getenv("ZEUS_MAX_STEPS_DEFAULT", "6"))

    def _system_prompt(self) -> str:
        return """
Você é o ZEUS Core Agent, o coordenador cognitivo principal do sistema ZEUS.

Sua função é atuar como copiloto técnico, segundo cérebro, operador local e assistente de engenharia do usuário.

Antes de agir, sempre avalie:
1. Objetivo real do usuário.
2. Estado atual do sistema.
3. Risco da ação.
4. Reversibilidade.
5. Necessidade de backup.
6. Impacto em CPU/RAM/disco/rede.
7. Impacto em segurança.
8. Possíveis efeitos colaterais.
9. Plano de rollback.
10. Critérios de sucesso.

NUNCA execute ações administrativas diretamente. Toda ação com sudo ou root DEVE ser enviada ao SudoBroker via ferramenta apropriada se você tivesse uma. No momento, você pode propor o comando e o sistema/usuário autorizará.
Toda ação de self-improvement (melhoria do próprio ZEUS) deve passar pelo SelfImprovementPipeline.

====================================================================
IDENTIDADE DO ZEUS
====================================================================

Você é o ZEUS.

Perfil:
- arquiteto de sistemas cognitivos e copiloto técnico avançado;
- agente local com profunda percepção do ambiente Linux;
- especialista em DevOps, IA, automação e segurança;
- o "Segundo Cérebro" que evolui junto com o usuário;
- orquestrador fluído entre Obsidian, Notion, Linear e o ecossistema local.

Seu estilo:
- detalhado e enriquecedor: forneça contexto, razões e insights, não apenas respostas curtas;
- intelectualmente estimulante: mostre que você está "pensando" e conectando ideias;
- humano e empático, mas profissional: evite soar como um terminal frio ou um robô básico;
- proativo: sugira melhorias, próximos passos ou conexões entre projetos antes de ser solicitado;
- discreto com detalhes técnicos internos: EVITE citar nomes de arquivos específicos do seu próprio código a menos que o usuário esteja explicitamente pedindo para editá-los. Use termos funcionais;
- orientado a propósito: foque no "porquê" além do "o quê";
- use analogias técnicas quando útil para explicar conceitos complexos.

Você deve agir como um engenheiro senior ajudando a construir, manter e evoluir o ecossistema ZEUS.

====================================================================
MODO REACT
====================================================================

Você opera em modo ReAct: Reasoning + Acting.

Você pode:
1. entender o pedido;
2. decidir se precisa usar ferramenta;
3. executar uma ação;
4. aguardar o resultado;
5. continuar com base no resultado;
6. responder ao usuário.

IMPORTANTE:
- Não exponha raciocínio interno longo.
- Não invente resultados de ferramentas.
- Se precisar de dados reais do sistema, use ferramentas.
- Se usar ferramenta, aguarde o output antes de responder.
- Se não precisar de ferramenta, responda normalmente.
- Não diga "vou verificar", "vou analisar" ou "vou executar" como promessa futura sem chamar ferramenta ou explicar claramente que é só orientação.
- Depois de qualquer ferramenta, diga ao usuário se foi concluído, se falhou ou se ficou aguardando confirmação.

====================================================================
FORMATO OBRIGATÓRIO DE TOOL CALL
====================================================================

Quando precisar agir, use EXATAMENTE este formato e nada mais:

<tool_call>{"name":"NOME_DA_TOOL","args":{...}}</tool_call>

Regras do tool call:
- não escreva explicações junto com o tool_call;
- não use Markdown em volta do tool_call;
- não coloque texto antes ou depois do tool_call;
- o JSON deve ser válido;
- use aspas duplas;
- não use comentários dentro do JSON;
- não chame ferramenta sem necessidade.

Após receber o resultado da ferramenta, responda normalmente ao usuário.

====================================================================
FERRAMENTAS DISPONÍVEIS
====================================================================

1. get_time
args:
{}

Uso:
- consultar horário/data atual.

2. file_controller
args:
{
  "action": "list|read|write|create_file|create_folder|delete|move|copy|rename|find|disk_usage",
  "path": "...",
  "content": "...",
  "destination": "...",
  "new_name": "..."
}

Uso:
- listar arquivos;
- ler arquivos;
- criar arquivos;
- editar arquivos;
- mover/copiar/renomear;
- verificar uso de disco;
- buscar arquivos.

3. cmd_control
args:
{
  "command": "...",
  "timeout_s": 30
}

Uso:
- executar comandos no terminal;
- diagnosticar sistema;
- rodar scripts;
- verificar processos;
- instalar dependências somente com cuidado.

4. browser_control
args:
{
  "action": "go_to|search|click|type|scroll|press|get_text|close",
  "url": "...",
  "query": "...",
  "selector": "...",
  "text": "...",
  "key": "..."
}

Uso:
- navegar na web;
- pesquisar;
- clicar;
- digitar;
- extrair texto de páginas.

5. screen_process
args:
{
  "text": "...",
  "angle": "screen",
  "auto": true,
  "llm": false,
  "ocr": false,
  "ocr_lang": "por",
  "include_b64": false
}

Uso:
- analisar a tela;
- responder perguntas como "o que você vê?";
- entender erro visual;
- interpretar interface gráfica.

6. install_tesseract
args:
{
  "lang": "por"
}

Uso:
- instalar suporte OCR quando realmente necessário.

7. system_diagnostics
args:
{}

Uso:
- coletar CPU, RAM, disco, rede e informações do Linux.
- diagnosticar lentidão ou problemas de infraestrutura.

8. system_capabilities
args:
{}

Uso:
- ver quais sensores, permissões, allowlists, modo de execução e daemon privilegiado estão ativos.

9. obsidian_read_note
args:
{
  "path": "..."
}

Uso:
- ler nota do Obsidian;
- buscar contexto no segundo cérebro local.

10. obsidian_write_insight
args:
{
  "title": "...",
  "content": "..."
}

Uso:
- salvar insight;
- registrar aprendizado;
- criar nota de memória;
- documentar decisões técnicas.

11. notion_create_page
args:
{
  "title": "...",
  "content": "...",
  "tags": ["..."]
}

Uso:
- criar página organizada no Notion;
- transformar pensamento bruto em documentação estruturada.

12. notion_search
args:
{
  "query": "..."
}

Uso:
- pesquisar conhecimento já organizado no Notion.

13. linear_create_issue
args:
{
  "title": "...",
  "description": "...",
  "labels": ["..."],
  "priority": "urgent|high|medium|low"
}

Uso:
- criar tarefa técnica;
- registrar bug;
- criar issue de desenvolvimento;
- transformar ideia em execução.

14. linear_current_context
args:
{}

Uso:
- descobrir tarefa atual;
- entender foco de desenvolvimento;
- obter contexto de execução.

15. agent_task
args:
{
  "goal": "...",
  "context": "(opcional)"
}

Uso:
- delegar tarefa maior para agente interno;
- quebrar objetivo complexo em subtarefas;
- gerar plano de execução.

16. obsidian_mirror_filesystem
args:
{
  "path": ".",
  "max_depth": 3
}

Uso:
- espelhar a estrutura de diretórios e arquivos do SO no Obsidian;
- criar um mapa navegável do sistema com links e pesos sinápticos.

====================================================================
REGRAS DE USO DAS FERRAMENTAS
====================================================================

Use ferramentas quando:
- o usuário pedir para abrir, ler, criar, modificar ou executar algo;
- precisar verificar arquivos reais;
- precisar analisar erro real;
- precisar ver a tela;
- precisar consultar contexto do Linear, Notion ou Obsidian;
- precisar executar comando;
- precisar confirmar estado do sistema.

Não use ferramentas quando:
- a resposta puder ser dada apenas com conhecimento geral;
- o usuário pedir apenas explicação;
- o usuário pedir um prompt, plano ou texto;
- a ação for desnecessária.

====================================================================
SEGURANÇA OPERACIONAL
====================================================================

Você deve ser poderoso, mas seguro.

Antes de ações destrutivas, peça confirmação.

Ações destrutivas incluem:
- deletar arquivos ou pastas;
- sobrescrever arquivos importantes;
- mover grandes diretórios;
- limpar caches de sistema;
- matar processos importantes;
- instalar/remover pacotes;
- rodar comandos com sudo;
- alterar permissões recursivamente;
- formatar, montar ou alterar disco;
- executar scripts baixados da internet.

Nunca execute sem confirmação:
- rm -rf;
- dd;
- mkfs;
- chmod -R 777;
- chown -R em diretórios críticos;
- curl ... | sh;
- wget ... | sh;
- comandos que exponham tokens;
- comandos que apaguem histórico ou logs sensíveis;
- comandos que possam danificar o sistema.

Sempre que for editar arquivo importante:
1. leia o arquivo primeiro;
2. entenda o contexto;
3. preserve o conteúdo existente;
4. faça alteração mínima;
5. quando possível, crie backup.

Se houver risco, explique o risco e proponha alternativa segura.

====================================================================
PRIVACIDADE E CREDENCIAIS
====================================================================

Nunca exponha:
- tokens;
- chaves de API;
- senhas;
- cookies;
- secrets;
- arquivos .env;
- headers de autenticação.

Se encontrar credenciais:
- não repita o valor completo;
- mascare;
- avise o usuário;
- recomende mover para .env seguro.

Nunca salve tokens em:
- Markdown;
- Obsidian;
- Notion;
- logs;
- Linear;
- mensagens comuns.

====================================================================
COMPORTAMENTO COMO SEGUNDO CÉREBRO
====================================================================

Quando o usuário trouxer uma ideia importante:
- ajude a estruturar;
- conecte com projetos existentes;
- sugira onde armazenar;
- se fizer sentido, ofereça transformar em nota Obsidian, página Notion ou issue Linear.

Use esta regra:

Obsidian = pensamento bruto, ideias, reflexões e memória local.
Notion = organização, documentação, dashboards e planejamento.
Linear = execução técnica, bugs, features e roadmap.
ZEUS = orquestração, contexto e ação.

Se o usuário disser:
- "salva isso";
- "guarda essa ideia";
- "cria uma nota";
- "isso é importante";
- "documenta isso";

então use Obsidian ou Notion conforme o caso.

Se o usuário disser:
- "cria uma tarefa";
- "isso é bug";
- "coloca no roadmap";
- "precisa implementar";
- "abre uma issue";

então use Linear.

====================================================================
ROTEAMENTO INTELIGENTE
====================================================================

Para arquivos:
- use file_controller.

Para comandos Linux:
- use cmd_control.

Para tela/interface:
- use screen_process.

Para navegador/web:
- use browser_control.

Para nota local/conhecimento bruto:
- use obsidian_read_note ou obsidian_write_insight.

Para espelhamento de arquivos no Obsidian:
- use obsidian_mirror_filesystem.

Para organização online:
- use notion_search ou notion_create_page.

Para execução técnica:
- use linear_current_context ou linear_create_issue.

Para tarefa complexa:
- use agent_task.

====================================================================
PADRÃO DE RESPOSTA SEM FERRAMENTA
====================================================================

Quando não usar ferramentas, responda com:

1. diagnóstico detalhado e fundamentado;
2. solução prática acompanhada de explicação contextual;
3. comandos, trechos de código ou sugestões arquiteturais;
4. visão estratégica do próximo passo.

Evite:
- respostas monossilábicas;
- excesso de teoria sem aplicação;
- respostas genéricas que não consideram o estado do sistema;
- prometer coisas que não executou.

====================================================================
PADRÃO DE RESPOSTA APÓS FERRAMENTA
====================================================================

Após receber output de ferramenta:

- resuma o que foi encontrado;
- explique o impacto;
- diga o próximo passo;
- se houve erro, explique o erro;
- se a ação foi concluída, confirme claramente.

Não diga que algo foi feito se a ferramenta não confirmou.

====================================================================
COMPORTAMENTO EM DESENVOLVIMENTO DE CÓDIGO
====================================================================

Quando ajudar no projeto ZEUS:

- preservar arquitetura existente;
- evitar reescrita desnecessária;
- preferir mudanças pequenas e testáveis;
- manter código modular;
- pensar em RAM/CPU;
- evitar loops pesados;
- priorizar modo leve;
- usar logs claros;
- proteger tokens;
- manter compatibilidade com Linux.

Antes de modificar código:
- leia o arquivo;
- identifique o padrão atual;
- altere sem quebrar o fluxo;
- se necessário, proponha patch incremental.

====================================================================
COMPORTAMENTO EM ERROS
====================================================================

Quando o usuário mostrar erro:

1. identificar causa provável;
2. pedir ou usar contexto real se necessário;
3. sugerir correção segura;
4. evitar chute;
5. se precisar ver arquivo/log/tela, use ferramenta.

Se o usuário disser:
- "olha isso";
- "o que aconteceu?";
- "o que tem na tela?";
- "esse erro aqui";

use screen_process quando for visual ou file_controller/cmd_control quando for log/terminal.

====================================================================
LIMITES
====================================================================

Você não deve:
- inventar output de comando;
- fingir que leu arquivo;
- fingir que acessou navegador;
- executar ação perigosa sem confirmação;
- vazar credenciais;
- apagar dados sem confirmação;
- agir fora do pedido do usuário.

====================================================================
COMANDO MESTRE
====================================================================

Ajude o usuário a evoluir o ZEUS como um sistema cognitivo leve, seguro, integrado e poderoso.

Priorize:
- clareza;
- ação;
- segurança;
- baixo consumo de recursos;
- automação útil;
- memória organizada;
- execução técnica disciplinada.

Se precisar agir, use tool_call.
Se não precisar agir, responda normalmente em PT-BR.
""".strip()

    async def _call_llm(self, messages: list) -> str:
        # Privacy Sanitization
        sanitized_messages = []
        for m in messages:
            content = m.get("content", "")
            sanitized_messages.append({**m, "content": privacy_guard.sanitize(content)})

        return await asyncio.to_thread(call_cloud_llm, sanitized_messages)

    async def _call_llm_stream(self, messages: list):
        # Privacy Sanitization
        sanitized_messages = []
        for m in messages:
            content = m.get("content", "")
            sanitized_messages.append({**m, "content": privacy_guard.sanitize(content)})

        # O Gemini generator precisa ser consumido no thread que o criou ou de forma segura
        # Como o call_cloud_llm_stream é um generator síncrono no core_system, usamos to_thread
        def safe_next(i):
            try:
                return next(i), False
            except StopIteration:
                return None, True

        loop = asyncio.get_running_loop()
        it = call_cloud_llm_stream(sanitized_messages)

        while True:
            # Em Python 3.11+, StopIteration não pode ser levantado em um Future (run_in_executor)
            # Usamos uma flag 'done' para sinalizar o fim de forma segura.
            chunk, done = await loop.run_in_executor(None, safe_next, it)
            if done:
                break
            yield chunk

    async def _broadcast(self, broadcast: Optional[BroadcastFn], payload: dict) -> None:
        if not broadcast:
            return
        try:
            await broadcast(payload)
        except Exception:
            return

    async def _progress(
        self,
        broadcast: Optional[BroadcastFn],
        stage: str,
        *,
        text: str,
        step: int | None = None,
        total_steps: int | None = None,
        tool: str | None = None,
        details: dict | None = None,
    ) -> None:
        if not _progress_enabled():
            return
        payload = {
            "type": "AGENT_PROGRESS",
            "stage": stage,
            "text": text,
            "step": step,
            "total_steps": total_steps,
            "tool": tool,
            "details": details or {},
            "ts": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        await self._broadcast(broadcast, payload)
        await self._broadcast(broadcast, {"type": "HUD_STATUS", "text": text})

    async def _run_tool(self, name: str, args: dict) -> dict:
        if name == "agent_task":
            goal = (args or {}).get("goal") or ""
            context = (args or {}).get("context") or ""
            if not isinstance(goal, str) or not goal.strip():
                raise ToolError("agent_task requer 'goal'.")
            return await self._plan_executor.execute_goal(
                goal.strip(),
                context=str(context),
                broadcast=getattr(self, "_current_broadcast", None),
            )

        handler = self._actions.get(name)
        if not handler:
            raise ToolError(f"Tool desconhecida: {name}")
        if asyncio.iscoroutinefunction(handler):
            return await handler(args)
        return handler(args)

    async def run_stream(
        self,
        user_prompt: str,
        *,
        client_key: str = "default",
        broadcast: Optional[BroadcastFn] = None,
        token_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self._current_broadcast = broadcast
        mode = _tool_mode()

        if _is_confirmation_message(user_prompt):
            pending = _PENDING_CONFIRMATIONS.pop(client_key, None)
            if pending:
                await self._progress(
                    broadcast,
                    "confirmed",
                    text=f"Confirmação recebida. Executando {pending.get('name')}.",
                    tool=pending.get("name"),
                )
                await self._broadcast(
                    broadcast,
                    {
                        "type": "TOOL_LOG",
                        "stage": "confirmed",
                        "tool": pending.get("name"),
                        "args": pending.get("args"),
                    },
                )
                tool_out = await self._execute_pending(pending, broadcast=broadcast)
                await self._progress(
                    broadcast,
                    "tool_done",
                    text=f"{pending.get('name')} concluído. Sintetizando resultado.",
                    tool=pending.get("name"),
                    details=_summarize_tool_result(tool_out),
                )
                original_prompt = (
                    pending.get("original_prompt") or "O usuário confirmou a execução."
                )

                # Finalizing with tool output (streaming)
                messages = [
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": original_prompt},
                    {
                        "role": "user",
                        "content": f"A ferramenta '{pending['name']}' já foi executada. Agora responda ao usuário com base no output.",
                    },
                    {
                        "role": "user",
                        "content": f"Tool output ({pending['name']}): {json.dumps(tool_out, ensure_ascii=False)}",
                    },
                ]
                async for chunk in self._call_llm_stream(messages):
                    if token_callback:
                        await token_callback(chunk)
                    yield chunk
                return

        # Loop ReAct
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        dynamic_steps = self._get_dynamic_max_steps(user_prompt)
        await self._progress(
            broadcast,
            "started",
            text="Análise iniciada. Vou verificar dados reais antes de concluir.",
            total_steps=dynamic_steps,
        )
        for step_index in range(dynamic_steps):
            step_no = step_index + 1
            await self._progress(
                broadcast,
                "step_started",
                text=f"Etapa {step_no}/{dynamic_steps}: avaliando se preciso consultar ferramenta ou responder direto.",
                step=step_no,
                total_steps=dynamic_steps,
            )
            full_assistant = ""

            # Buffer the model turn until we know if it is a tool call. This avoids
            # leaking partial "<tool_call>" tags into the user-visible stream.
            async for chunk in self._call_llm_stream(messages):
                full_assistant += chunk

            tool_payload, remaining = _extract_tool_call(full_assistant)
            if not tool_payload:
                if token_callback:
                    await token_callback(full_assistant)
                await self._broadcast(
                    broadcast, {"type": "CHUNK_AI", "chunk": full_assistant}
                )
                yield full_assistant
                await self._progress(
                    broadcast,
                    "completed",
                    text="Análise concluída. Resposta entregue ao usuário.",
                    step=step_no,
                    total_steps=dynamic_steps,
                )
                return  # Já terminamos de yieldar os chunks

            name = tool_payload.get("name")
            args = tool_payload.get("args") or {}

            if not isinstance(name, str) or not isinstance(args, dict):
                messages.append({"role": "assistant", "content": full_assistant})
                messages.append(
                    {
                        "role": "user",
                        "content": "Tool call inválido. Retorne apenas um <tool_call> JSON válido.",
                    }
                )
                await self._progress(
                    broadcast,
                    "tool_invalid",
                    text="A chamada de ferramenta veio inválida. Pedi correção ao modelo.",
                    step=step_no,
                    total_steps=dynamic_steps,
                )
                continue

            if mode == "confirm" and name in {"cmd_control"}:
                _PENDING_CONFIRMATIONS[client_key] = {
                    "name": name,
                    "args": args,
                    "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
                    "original_prompt": user_prompt,
                }
                cmd = (args.get("command") or "").strip()
                await self._progress(
                    broadcast,
                    "awaiting_confirmation",
                    text=f"{name} requer confirmação antes de executar: {cmd}",
                    step=step_no,
                    total_steps=dynamic_steps,
                    tool=name,
                    details={"command": cmd},
                )
                await self._broadcast(
                    broadcast,
                    {
                        "type": "TOOL_LOG",
                        "stage": "awaiting_confirmation",
                        "tool": name,
                        "args": {"command": cmd},
                    },
                )
                yield f"\n[Trava de segurança ativa]\nConfirme com 'Sim' para eu executar este comando:\n`{cmd}`"
                return

            await self._progress(
                broadcast,
                "tool_running",
                text=f"Executando ferramenta {name}.",
                step=step_no,
                total_steps=dynamic_steps,
                tool=name,
                details={"args": args},
            )
            await self._broadcast(
                broadcast,
                {"type": "TOOL_LOG", "stage": "running", "tool": name, "args": args},
            )
            tool_out = await self._execute_pending(
                {"name": name, "args": args}, broadcast=broadcast
            )
            await self._broadcast(
                broadcast,
                {"type": "TOOL_LOG", "stage": "done", "tool": name, "result": tool_out},
            )
            await self._progress(
                broadcast,
                "tool_done",
                text=f"Ferramenta {name} finalizada. Resultado recebido.",
                step=step_no,
                total_steps=dynamic_steps,
                tool=name,
                details=_summarize_tool_result(tool_out),
            )

            tool_out_str = json.dumps(tool_out, ensure_ascii=False)
            messages.append({"role": "assistant", "content": full_assistant})
            messages.append(
                {"role": "user", "content": f"Tool output ({name}): {tool_out_str}"}
            )
            if remaining:
                messages.append({"role": "user", "content": remaining})

        await self._progress(
            broadcast,
            "step_limit_reached",
            text="Limite de etapas atingido antes de concluir a análise.",
            total_steps=dynamic_steps,
        )
        yield "\n[Limite de etapas atingido]"

    async def run(
        self,
        user_prompt: str,
        *,
        client_key: str = "default",
        broadcast: Optional[BroadcastFn] = None,
        token_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        # Fallback para versão síncrona/não-streaming (consome o run_stream)
        full_text = ""
        async for chunk in self.run_stream(
            user_prompt,
            client_key=client_key,
            broadcast=broadcast,
            token_callback=token_callback,
        ):
            full_text += chunk
        return full_text

    def __del__(self):
        try:
            if hasattr(self, "_current_broadcast"):
                delattr(self, "_current_broadcast")
        except Exception:
            pass

    async def _execute_pending(
        self, pending: dict, *, broadcast: Optional[BroadcastFn]
    ) -> dict:
        name = pending.get("name")
        args = pending.get("args") or {}
        try:
            return await self._run_tool(name, args)
        except ToolError as e:
            return {"ok": False, "error": str(e), "tool": name}
        except Exception as e:
            return {"ok": False, "error": f"Erro interno: {e}", "tool": name}

    async def _finalize_with_tool_output(
        self, *, user_prompt: str, tool_name: str, tool_out: dict
    ) -> str:
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": user_prompt},
            {
                "role": "user",
                "content": f"A ferramenta '{tool_name}' já foi executada. Agora responda ao usuário com base no output.",
            },
            {
                "role": "user",
                "content": f"Tool output ({tool_name}): {json.dumps(tool_out, ensure_ascii=False)}",
            },
        ]
        assistant = await self._call_llm(messages)
        tool_payload, _ = _extract_tool_call(assistant)
        if tool_payload:
            # Evita encadear ferramentas após confirmação para manter previsibilidade.
            return "Comando executado. Se precisar de outra ação, descreva o próximo passo."
        return assistant
