import os
import json
import requests
import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# --- CARREGADOR DE AMBIENTE LOCAL (.env) ---
def _load_local_env():
    # Procura o .env na raiz do projeto (um nível acima de core_modules)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_local_env()

# Configurações de API
LLM_PROVIDER = os.getenv("NEXUS_LLM_PROVIDER", "").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", os.getenv("NEXUS_OPENAI_MODEL", "gpt-4o-mini"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_URL = os.getenv("NEXUS_LLM_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_API_KEY = os.getenv("NEXUS_LLM_API_KEY", os.getenv("OLLAMA_API_KEY", ""))
MODEL = os.getenv("NEXUS_LLM_MODEL", "gemma4:31b-cloud")
DISABLE_OLLAMA = os.getenv("NEXUS_DISABLE_OLLAMA", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PREFER_OLLAMA = os.getenv("NEXUS_PREFER_OLLAMA", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MAX_PROMPT_CHARS = int(os.getenv("NEXUS_MAX_PROMPT_CHARS", "16000") or "16000")

GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# Cliente Global do Gemini (Novo SDK google-genai)
_GEMINI_CLIENT = None
if GEMINI_API_KEY and genai:
    try:
        _GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f" [NEXUS] Erro ao inicializar cliente Gemini: {e}")
elif GEMINI_API_KEY:
    print(
        " [NEXUS] google-genai não está instalado; Gemini desativado, usando fallback."
    )


def _extract_message_content(data):
    """Aceita formatos estilo Ollama e compatíveis com OpenAI."""
    if isinstance(data, dict):
        # Formato Nativo Ollama
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content

        # Formato OpenAI-compatible
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0] or {}
            if isinstance(choice, dict):
                message = choice.get("message") or {}
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content

        # Formato Simples
        content = data.get("content")
        if isinstance(content, str) and content.strip():
            return content

    return None


try:
    from nexus_state import BlackboardRust

    RUST_STATE_AVAILABLE = True
except ImportError:
    RUST_STATE_AVAILABLE = False


class Blackboard:
    """Estado global compartilhado entre os agentes."""

    def __init__(self):
        if RUST_STATE_AVAILABLE:
            self.rust_blackboard = BlackboardRust()
            # Inicializar chaves padrão
            self.update("current_goal", None)
            self.update("plan", None)
            self.update("execution_result", None)
            self.update("metrics", None)
            self.update("status", "IDLE")
            self.update("context_fragment", "")
        else:
            self.rust_blackboard = None
            self.state = {
                "current_goal": None,
                "plan": None,
                "execution_result": None,
                "metrics": None,
                "status": "IDLE",
                "context_fragment": "",
            }

    def update(self, key, value):
        if self.rust_blackboard:
            self.rust_blackboard.set(key, json.dumps(value))
        else:
            self.state[key] = value

    def get(self, key):
        if self.rust_blackboard:
            json_val = self.rust_blackboard.get(key)
            if json_val:
                return json.loads(json_val)
            return None
        return self.state.get(key)


class CloudAgent:
    """Classe base para agentes que consomem a LLM."""

    def _call_llm(self, system_prompt, user_prompt):
        return call_cloud_llm(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )


def _format_messages_for_genai(messages):
    """Converte formato OpenAI/Ollama para o formato nativo do novo SDK google-genai."""
    if types is None:
        raise RuntimeError("google-genai não está instalado.")

    system_instruction = None
    contents = []

    for m in messages:
        role = m["role"]
        content = m["content"]

        if role == "system":
            system_instruction = content
        elif role == "user":
            contents.append(
                types.Content(role="user", parts=[types.Part(text=content)])
            )
        elif role in ["assistant", "model"]:
            contents.append(
                types.Content(role="model", parts=[types.Part(text=content)])
            )

    return system_instruction, contents


def _trim_messages(messages):
    """
    Controla o tamanho do prompt para reduzir latencia e evitar estouro de contexto.
    Mantem as mensagens mais recentes e trunca conteúdos muito longos.
    """
    if not isinstance(messages, list):
        return messages

    max_chars = max(2000, MAX_PROMPT_CHARS)
    trimmed = []
    used = 0

    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        if len(content) > 6000:
            content = content[-6000:]
        chunk = len(content)
        if trimmed and used + chunk > max_chars:
            break
        trimmed.append({"role": role, "content": content})
        used += chunk

    return list(reversed(trimmed)) or [{"role": "user", "content": "Continue."}]


def _use_openai() -> bool:
    if LLM_PROVIDER == "openai":
        return True
    return bool(
        OPENAI_API_KEY
        and not GEMINI_API_KEY
        and LLM_PROVIDER not in {"gemini", "ollama"}
    )


def _use_ollama() -> bool:
    return (LLM_PROVIDER == "ollama" or PREFER_OLLAMA) and not DISABLE_OLLAMA


def _active_llm_provider() -> str:
    if _use_openai():
        return "openai"
    if _use_ollama():
        return "ollama"
    if GEMINI_API_KEY and _GEMINI_CLIENT:
        return "gemini"
    if not DISABLE_OLLAMA:
        return "ollama"
    return LLM_PROVIDER or "none"


def get_llm_status() -> dict:
    provider = _active_llm_provider()
    model = {
        "openai": OPENAI_MODEL,
        "gemini": GEMINI_MODEL_NAME,
        "ollama": MODEL,
    }.get(provider)
    configured = {
        "openai": bool(OPENAI_API_KEY),
        "gemini": bool(GEMINI_API_KEY and _GEMINI_CLIENT),
        "ollama": not DISABLE_OLLAMA,
    }.get(provider, False)

    return {
        "provider": provider,
        "model": model,
        "configured": configured,
        "streaming": provider in {"openai", "gemini"},
        "fallbacks": {
            "openai_configured": bool(OPENAI_API_KEY),
            "gemini_configured": bool(GEMINI_API_KEY and _GEMINI_CLIENT),
            "ollama_enabled": not DISABLE_OLLAMA,
        },
        "base_url": OPENAI_BASE_URL
        if provider == "openai"
        else OLLAMA_URL
        if provider == "ollama"
        else None,
    }


def _format_openai_error(response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = {}

    error = payload.get("error") if isinstance(payload, dict) else {}
    code = (error or {}).get("code") or ""
    message = (error or {}).get("message") or response.text[:300]

    if response.status_code == 401:
        return "OpenAI API key inválida ou ausente. Verifique OPENAI_API_KEY no .env."
    if response.status_code == 429:
        if code == "insufficient_quota" or "quota" in message.lower():
            return "OpenAI sem quota/billing disponível. Ative billing ou adicione créditos na plataforma da API."
        return "OpenAI retornou limite de uso/rate limit (429). Tente novamente em instantes."
    if response.status_code == 404:
        return f"Modelo OpenAI não encontrado ou sem acesso: {OPENAI_MODEL}."
    return f"OpenAI API retornou {response.status_code}: {message}"


def _format_messages_for_openai(messages):
    """Mantém compatibilidade com Chat Completions."""
    formatted = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or "user"
        content = m.get("content", "")
        if role == "model":
            role = "assistant"
        if role not in {"system", "developer", "user", "assistant", "tool"}:
            role = "user"
        formatted.append({"role": role, "content": str(content)})
    return formatted or [{"role": "user", "content": "Continue."}]


def _call_openai_chat(messages, *, stream: bool = False):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    payload = {
        "model": OPENAI_MODEL,
        "messages": _format_messages_for_openai(messages),
        "stream": stream,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    return requests.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        json=payload,
        headers=headers,
        stream=stream,
        timeout=300,
    )


def call_cloud_llm(messages):
    messages = _trim_messages(messages)
    if _use_openai():
        try:
            response = _call_openai_chat(messages, stream=False)
            if response.status_code == 200:
                content = _extract_message_content(response.json())
                if content:
                    return content
                return f"Error: No content in OpenAI response payload ({response.text[:200]})"
            return f"Error: {_format_openai_error(response)}"
        except Exception as e:
            return f"OpenAI Connection Error: {str(e)}"

    if _use_ollama():
        return _call_ollama_chat(messages)

    # Prioridade para o Gemini se a chave existir
    if GEMINI_API_KEY and _GEMINI_CLIENT:
        try:
            sys_inst, contents = _format_messages_for_genai(messages)

            # Debug parameters
            print(
                f"DEBUG GEMINI: model={GEMINI_MODEL_NAME} sys_inst={sys_inst[:50] if sys_inst else None} history_len={len(contents)}"
            )

            config = None
            if sys_inst:
                config = types.GenerateContentConfig(system_instruction=sys_inst)

            if contents:
                response = _GEMINI_CLIENT.models.generate_content(
                    model=GEMINI_MODEL_NAME, contents=contents, config=config
                )
            else:
                return "Error: No messages to process."

            if response.text:
                return response.text
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower():
                print(f"\n[NEXUS WARNING] Quota do Gemini excedida (429).")
                print(
                    f"Considere ativar o Ollama (.env: NEXUS_DISABLE_OLLAMA=0) ou aguardar o reset da quota.\n"
                )
                return f"Error: Gemini Quota Exceeded (429). {err_msg[:100]}"

            import traceback

            traceback.print_exc()
            print(f" [NEXUS] Erro no Gemini, fallback para Ollama: {e}")

    if DISABLE_OLLAMA:
        return "Error: Gemini unavailable and NEXUS_DISABLE_OLLAMA=1."

    return _call_ollama_chat(messages)


def _call_ollama_chat(messages):
    headers = {
        "Content-Type": "application/json",
    }

    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    use_generate_endpoint = OLLAMA_URL.rstrip("/").endswith("/api/generate")
    if use_generate_endpoint:
        prompt = "\n\n".join(
            f"{(m.get('role') or 'user').upper()}: {m.get('content', '')}"
            for m in messages
            if isinstance(m, dict)
        )
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
        }
    else:
        payload = {
            "model": MODEL,
            "messages": messages,
            "stream": False,
        }

    try:
        response = requests.post(OLLAMA_URL, json=payload, headers=headers, timeout=300)

        if response.status_code == 200:
            data = response.json()
            if use_generate_endpoint:
                generated = data.get("response")
                if isinstance(generated, str) and generated.strip():
                    return generated
            content = _extract_message_content(data)
            if content:
                return content
            return f"Error: No content in response payload ({json.dumps(data, ensure_ascii=False)[:200]})"

        return f"Error: {_format_ollama_error(response)}"
    except Exception as e:
        return f"Connection Error: {str(e)}"


def _format_ollama_error(response):
    body = response.text[:300]
    if response.status_code == 401:
        return (
            "Ollama Cloud nao autenticado. Execute `ollama signin` para usar "
            "modelos cloud via http://127.0.0.1:11434, ou configure "
            "OLLAMA_API_KEY/NEXUS_LLM_API_KEY para acesso autenticado."
        )
    if response.status_code == 404:
        return (
            f"Modelo Ollama nao encontrado: {MODEL}. Confirme o nome em "
            "`ollama list` ou ajuste NEXUS_LLM_MODEL."
        )
    return f"API returned {response.status_code} - {body}"


def call_cloud_llm_stream(messages):
    """Versão streaming para interação em tempo real."""
    messages = _trim_messages(messages)
    if _use_openai():
        try:
            response = _call_openai_chat(messages, stream=True)
            if response.status_code != 200:
                yield f"Error: {_format_openai_error(response)}"
                return

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                data = raw_line[len("data: ") :].strip()
                if data == "[DONE]":
                    return
                try:
                    payload = json.loads(data)
                    delta = (
                        (payload.get("choices") or [{}])[0].get("delta") or {}
                    ).get("content")
                    if delta:
                        yield delta
                except Exception:
                    continue
            return
        except Exception as e:
            yield f"OpenAI Stream Error: {str(e)}"
            return

    if _use_ollama():
        yield _call_ollama_chat(messages)
        return

    if GEMINI_API_KEY and _GEMINI_CLIENT:
        try:
            sys_inst, contents = _format_messages_for_genai(messages)

            config = None
            if sys_inst:
                config = types.GenerateContentConfig(system_instruction=sys_inst)

            if contents:
                response = _GEMINI_CLIENT.models.generate_content_stream(
                    model=GEMINI_MODEL_NAME, contents=contents, config=config
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower():
                yield f"[QUOTA EXCEEDED] O limite de uso do Gemini foi atingido. Por favor, aguarde ou ative o Ollama."
                return

            import traceback

            traceback.print_exc()
            print(f" [NEXUS] Erro no Gemini Stream: {e}")

    if DISABLE_OLLAMA:
        yield "Error: Gemini stream unavailable and NEXUS_DISABLE_OLLAMA=1."
        return

    # Fallback simples (não-streaming ou Ollama stream se implementado futuramente)
    yield call_cloud_llm(messages)


class LibrarianAgent:
    """Agente responsável pela gestão de memória e filtragem de contexto (RAG Lite)."""

    def __init__(self, core_path, vector_memory=None):
        self.core_path = core_path
        self.vector_memory = vector_memory

    def get_relevant_context(self, query):
        relevant_data = []

        # 1. Busca semântica real usando ChromaDB (RAG Verdadeiro)
        if self.vector_memory:
            try:
                rag_context = self.vector_memory.search_context(query, top_k=5)
                if rag_context:
                    relevant_data.append(
                        f"--- MEMÓRIA SEMÂNTICA (RAG) ---\n{rag_context}\n------------------------------"
                    )
            except Exception as e:
                print(f"RAG Error: {e}")

        # 2. DNA (Sempre incluir as instruções centrais)
        dna_path = os.path.join(self.core_path, "07 - DNA.md")
        if os.path.exists(dna_path):
            with open(dna_path, "r", encoding="utf-8") as f:
                relevant_data.append(f"--- DNA CORE ---\n{f.read()}\n----------------")

        return "\n\n".join(relevant_data)


class StrategistAgent(CloudAgent):
    """Agente Planner: Define a estratégia via LLM."""

    def plan(self, blackboard, user_input):
        system_prompt = (
            "Você é o STRATEGIST do NEXUS. Analise o contexto e crie um plano técnico MULTI-ETAPAS detalhado.\n"
            "Seu plano DEVE conter as seguintes seções:\n"
            "1. Objetivo e Diagnóstico\n"
            "2. Arquivos Envolvidos\n"
            "3. Riscos e Impacto (CPU/RAM/Disco)\n"
            "4. Passo a Passo Técnico\n"
            "5. Fallbacks e Plano de Rollback\n"
            "6. Nível de Autonomia Necessário (Requer SudoBroker?)\n"
            "7. Critérios de Sucesso"
        )
        user_prompt = (
            f"Contexto: {blackboard.get('context_fragment')}\nObjetivo: {user_input}"
        )

        plan = self._call_llm(system_prompt, user_prompt)
        blackboard.update("plan", plan)
        blackboard.update("status", "EXECUTING")
        return plan


class OperatorAgent(CloudAgent):
    """Agente que propõe comandos técnicos, sem executá-los localmente."""

    def _validate_commands(self, commands: str) -> bool:
        """Verifica a presença de comandos destrutivos."""
        blacklist = [
            "rm -rf /",
            "rm -rf *",
            "mkfs",
            "dd if=",
            "chmod 777",
            "chown -R root",
        ]
        cmd_lower = commands.lower()
        for bad_cmd in blacklist:
            if bad_cmd in cmd_lower:
                return False
        return True

    def execute(self, blackboard):
        system_prompt = (
            "Você é o OPERATOR do NEXUS. Transforme o plano estratégico em ações ou comandos seguros.\n"
            "REGRAS OBRIGATÓRIAS:\n"
            "1. Prefira comandos idempotentes.\n"
            "2. Exija backup antes de alterações.\n"
            "3. Proponha dry-run quando possível.\n"
            "4. NUNCA use sudo diretamente (ex: sudo apt update). Se precisar de admin, delegue para o SudoBroker.\n"
            "5. NUNCA execute comandos destrutivos (rm -rf /, dd, mkfs, chmod -R 777).\n"
            "6. Se for um patch em código, proponha patches pequenos."
        )
        user_prompt = f"Plano: {blackboard.get('plan')}"

        commands = self._call_llm(system_prompt, user_prompt)

        # O Operator propõe. A execução será gerenciada pela engine ReAct do agent.py ou pelo SudoBroker.
        result = {
            "mode": "PROPOSAL",
            "commands": commands,
            "executed": False,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        blackboard.update("execution_result", result)
        blackboard.update("status", "ANALYZING")
        return result


class CriticAgent(CloudAgent):
    """Agente Analyzer: valida um plano e sua proposta de execução."""

    def analyze(self, blackboard):
        system_prompt = (
            "Você é o CRITIC do NEXUS. Analise a proposta de execução e o plano.\n"
            "Você DEVE BLOQUEAR a execução se:\n"
            "- A ação usa sudo ou shell como root diretamente (sem SudoBroker).\n"
            "- Modifica /etc sem backup.\n"
            "- Remove arquivos críticos.\n"
            "- Modifica código do próprio NEXUS sem rollback.\n"
            "- A resposta agrupa contextos muito antigos (concatenação indevida).\n\n"
            "Responda EXATAMENTE com uma das palavras-chave na primeira linha: SUCCESS, REVISE, BLOCK ou NEED_USER_CONFIRMATION, seguida da sua justificativa."
        )
        execution_result = blackboard.get("execution_result")
        serialized_result = json.dumps(execution_result, ensure_ascii=False, indent=2)
        user_prompt = (
            f"Plano original: {blackboard.get('plan')}\n"
            f"Proposta técnica: {serialized_result}"
        )

        metric = self._call_llm(system_prompt, user_prompt)
        first_line = metric.strip().split("\n")[0].upper()

        status = "UNKNOWN"
        for kw in ["SUCCESS", "REVISE", "BLOCK", "NEED_USER_CONFIRMATION"]:
            if kw in first_line:
                status = kw
                break

        if status == "UNKNOWN":
            status = "REVISE"

        blackboard.update("status", status)
        blackboard.update("metrics", metric)
        return metric


class ObserverAgent(CloudAgent):
    """Agente de Vigilância: Analisa o contexto visual do sistema."""

    def __init__(self, core_path):
        self.core_path = core_path

    def observe_screen(
        self, blackboard, question="O que está acontecendo na tela agora?"
    ):
        try:
            from nexus_core.vision import capture_screen, analyze_image_with_llm

            # 1. Captura a tela
            shot = capture_screen()
            path = shot.get("path")

            if not path:
                return "Erro ao capturar tela."

            # 2. Analisa com LLM Vision
            analysis = analyze_image_with_llm(path, question=question)
            answer = analysis.get("answer", "Sem resposta da visão.")

            # 3. Atualiza Blackboard
            visual_context = {
                "last_observation": answer,
                "timestamp": datetime.datetime.now().isoformat(),
                "screen_path": path,
            }
            blackboard.update("visual_context", visual_context)

            return answer
        except Exception as e:
            return f"Erro na visão contextual: {e}"
