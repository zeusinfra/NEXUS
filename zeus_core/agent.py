import asyncio
import datetime as _dt
import json
import os
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from zeus_core.core_system import call_cloud_llm, call_cloud_llm_stream
from zeus_core.executor import PlanExecutor
from zeus_core.tools import ToolError
from zeus_core.actions import get_actions


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
        l = payload_str.find("{")
        r = payload_str.rfind("}")
        if l != -1 and r != -1 and r > l:
            try:
                payload = json.loads(payload_str[l : r + 1])
            except Exception:
                payload = None

    remaining = "\n".join([p for p in [before, after] if p])
    return payload, remaining


def _is_confirmation_message(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {"sim", "s", "confirmo", "confirmar", "ok"}


class Agent:
    def __init__(self, *, max_steps: int = 6):
        self.max_steps = max_steps
        self._actions = get_actions()
        self._plan_executor = PlanExecutor()

    def _system_prompt(self) -> str:
        return (
            "Você é o ZEUS em modo Agente ReAct (Reasoning + Acting).\n"
            "Quando precisar agir, use EXATAMENTE este formato e nada mais:\n"
            "<tool_call>{\"name\":\"NOME_DA_TOOL\",\"args\":{...}}</tool_call>\n\n"
            "Ferramentas disponíveis:\n"
            "- get_time args: {}\n"
            "- file_controller args: {\"action\": \"list|read|write|create_file|create_folder|delete|move|copy|rename|find|disk_usage\", \"path\": \"...\", \"content\": \"...\", \"destination\": \"...\", \"new_name\": \"...\"}\n"
            "- cmd_control args: {\"command\": \"...\", \"timeout_s\": 30}\n"
            "- browser_control args: {\"action\": \"go_to|search|click|type|scroll|press|get_text|close\", \"url\": \"...\", \"query\": \"...\", \"selector\": \"...\", \"text\": \"...\", \"key\": \"...\"}\n"
            "- screen_process args: {\"text\": \"...\", \"angle\": \"screen\", \"auto\": true, \"llm\": false, \"ocr\": false, \"ocr_lang\": \"por\", \"include_b64\": false}\n"
            "- install_tesseract args: {\"lang\": \"por\"}\n"
            "- obsidian_read_note args: {\"path\": \"...\"}\n"
            "- obsidian_write_insight args: {\"title\": \"...\", \"content\": \"...\"}\n"
            "- notion_create_page args: {\"title\": \"...\", \"content\": \"...\", \"tags\": [\"...\"]}\n"
            "- notion_search args: {\"query\": \"...\"}\n"
            "- linear_create_issue args: {\"title\": \"...\", \"description\": \"...\", \"labels\": [\"...\"], \"priority\": \"urgent|high|medium|low\"}\n"
            "- linear_current_context args: {}\n"
            "- agent_task args: {\"goal\": \"...\", \"context\": \"(opcional)\"}\n\n"
            "Regras:\n"
            "- Se você usar uma ferramenta, aguarde o output antes de responder ao usuário.\n"
            "- Se não precisar de ferramenta, responda normalmente em PT-BR.\n"
            "- Seja direto e seguro; leia arquivos antes de sobrescrever quando útil.\n"
            "- Se o usuário perguntar o que está na tela / 'o que você vê', use screen_process.\n"
        )

    async def _call_llm(self, messages: list) -> str:
        return await asyncio.to_thread(call_cloud_llm, messages)

    async def _call_llm_stream(self, messages: list):
        # O Gemini generator precisa ser consumido no thread que o criou ou de forma segura
        # Como o call_cloud_llm_stream é um generator síncrono no core_system, usamos to_thread
        def safe_next(i):
            try:
                return next(i), False
            except StopIteration:
                return None, True

        loop = asyncio.get_running_loop()
        it = call_cloud_llm_stream(messages)
        
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
                original_prompt = pending.get("original_prompt") or "O usuário confirmou a execução."
                
                # Finalizing with tool output (streaming)
                messages = [
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": original_prompt},
                    {"role": "user", "content": f"A ferramenta '{pending['name']}' já foi executada. Agora responda ao usuário com base no output."},
                    {"role": "user", "content": f"Tool output ({pending['name']}): {json.dumps(tool_out, ensure_ascii=False)}"},
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

        for _ in range(self.max_steps):
            full_assistant = ""
            is_tool_call = False
            
            # Tentamos detectar se é um tool call logo no início
            async for chunk in self._call_llm_stream(messages):
                full_assistant += chunk
                # Se ainda não detectamos tool call, mas o texto começa a parecer um, aguardamos
                if not is_tool_call and _TOOL_TAG_OPEN in full_assistant:
                    is_tool_call = True
                
                if not is_tool_call:
                    if token_callback:
                        await token_callback(chunk)
                    await self._broadcast(broadcast, {"type": "CHUNK_AI", "chunk": chunk})
                    yield chunk
            
            tool_payload, remaining = _extract_tool_call(full_assistant)
            if not tool_payload:
                return # Já terminamos de yieldar os chunks

            name = tool_payload.get("name")
            args = tool_payload.get("args") or {}
            
            if not isinstance(name, str) or not isinstance(args, dict):
                messages.append({"role": "assistant", "content": full_assistant})
                messages.append({"role": "user", "content": "Tool call inválido. Retorne apenas um <tool_call> JSON válido."})
                continue

            if mode == "confirm" and name in {"cmd_control"}:
                _PENDING_CONFIRMATIONS[client_key] = {
                    "name": name,
                    "args": args,
                    "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
                    "original_prompt": user_prompt,
                }
                cmd = (args.get("command") or "").strip()
                await self._broadcast(broadcast, {"type": "TOOL_LOG", "stage": "awaiting_confirmation", "tool": name, "args": {"command": cmd}})
                yield f"\n[Trava de segurança ativa]\nConfirme com 'Sim' para eu executar este comando:\n`{cmd}`"
                return

            await self._broadcast(broadcast, {"type": "TOOL_LOG", "stage": "running", "tool": name, "args": args})
            tool_out = await self._execute_pending({"name": name, "args": args}, broadcast=broadcast)
            await self._broadcast(broadcast, {"type": "TOOL_LOG", "stage": "done", "tool": name, "result": tool_out})

            tool_out_str = json.dumps(tool_out, ensure_ascii=False)
            messages.append({"role": "assistant", "content": full_assistant})
            messages.append({"role": "user", "content": f"Tool output ({name}): {tool_out_str}"})
            if remaining:
                messages.append({"role": "user", "content": remaining})

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

    async def _execute_pending(self, pending: dict, *, broadcast: Optional[BroadcastFn]) -> dict:
        name = pending.get("name")
        args = pending.get("args") or {}
        try:
            return await self._run_tool(name, args)
        except ToolError as e:
            return {"ok": False, "error": str(e), "tool": name}
        except Exception as e:
            return {"ok": False, "error": f"Erro interno: {e}", "tool": name}

    async def _finalize_with_tool_output(self, *, user_prompt: str, tool_name: str, tool_out: dict) -> str:
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": user_prompt},
            {"role": "user", "content": f"A ferramenta '{tool_name}' já foi executada. Agora responda ao usuário com base no output."},
            {"role": "user", "content": f"Tool output ({tool_name}): {json.dumps(tool_out, ensure_ascii=False)}"},
        ]
        assistant = await self._call_llm(messages)
        tool_payload, _ = _extract_tool_call(assistant)
        if tool_payload:
            # Evita encadear ferramentas após confirmação para manter previsibilidade.
            return "Comando executado. Se precisar de outra ação, descreva o próximo passo."
        return assistant
