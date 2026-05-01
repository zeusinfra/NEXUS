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
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

_load_local_env()

# Configurações de API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_URL = os.getenv("ZEUS_LLM_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_API_KEY = os.getenv("ZEUS_LLM_API_KEY", os.getenv("ZEUS_OPENWEBUI_API_KEY", ""))
MODEL = os.getenv("ZEUS_LLM_MODEL", "gemma4:31b-cloud")
DISABLE_OLLAMA = os.getenv("ZEUS_DISABLE_OLLAMA", "0").strip().lower() in {"1", "true", "yes", "on"}
MAX_PROMPT_CHARS = int(os.getenv("ZEUS_MAX_PROMPT_CHARS", "16000") or "16000")

GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# Cliente Global do Gemini (Novo SDK google-genai)
_GEMINI_CLIENT = None
if GEMINI_API_KEY and genai:
    try:
        _GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f" [ZEUS] Erro ao inicializar cliente Gemini: {e}")
elif GEMINI_API_KEY:
    print(" [ZEUS] google-genai não está instalado; Gemini desativado, usando fallback.")

def _extract_message_content(data):
    """Aceita formatos estilo Ollama e compatíveis com OpenAI."""
    if isinstance(data, dict):
        # Formato Nativo Ollama
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content

        # Formato OpenAI/OpenWebUI
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

class Blackboard:
    """Estado global compartilhado entre os agentes."""

    def __init__(self):
        self.state = {
            "current_goal": None,
            "plan": None,
            "execution_result": None,
            "metrics": None,
            "status": "IDLE",
            "context_fragment": "",
        }

    def update(self, key, value):
        self.state[key] = value

    def get(self, key):
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
            contents.append(types.Content(role="user", parts=[types.Part(text=content)]))
        elif role in ["assistant", "model"]:
            contents.append(types.Content(role="model", parts=[types.Part(text=content)]))
            
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

def call_cloud_llm(messages):
    messages = _trim_messages(messages)
    # Prioridade para o Gemini se a chave existir
    if GEMINI_API_KEY and _GEMINI_CLIENT:
        try:
            sys_inst, contents = _format_messages_for_genai(messages)
            
            # Debug parameters
            print(f"DEBUG GEMINI: model={GEMINI_MODEL_NAME} sys_inst={sys_inst[:50] if sys_inst else None} history_len={len(contents)}")

            config = None
            if sys_inst:
                config = types.GenerateContentConfig(system_instruction=sys_inst)
            
            if contents:
                response = _GEMINI_CLIENT.models.generate_content(
                    model=GEMINI_MODEL_NAME,
                    contents=contents,
                    config=config
                )
            else:
                return "Error: No messages to process."

            if response.text:
                return response.text
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower():
                print(f"\n[ZEUS WARNING] Quota do Gemini excedida (429).")
                print(f"Considere ativar o Ollama (.env: ZEUS_DISABLE_OLLAMA=0) ou aguardar o reset da quota.\n")
                return f"Error: Gemini Quota Exceeded (429). {err_msg[:100]}"
            
            import traceback
            traceback.print_exc()
            print(f" [ZEUS] Erro no Gemini, fallback para Ollama: {e}")

    if DISABLE_OLLAMA:
        return "Error: Gemini unavailable and ZEUS_DISABLE_OLLAMA=1."

    # Fallback para Ollama
    headers = {
        "Content-Type": "application/json",
    }
    
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
    }
    
    try:
        response = requests.post(
            OLLAMA_URL, json=payload, headers=headers, timeout=300
        )
        
        if response.status_code == 200:
            data = response.json()
            content = _extract_message_content(data)
            if content:
                return content
            return f"Error: No content in response payload ({json.dumps(data, ensure_ascii=False)[:200]})"

        return f"Error: API returned {response.status_code} - {response.text[:200]}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

def call_cloud_llm_stream(messages):
    """Versão streaming para interação em tempo real."""
    messages = _trim_messages(messages)
    if GEMINI_API_KEY and _GEMINI_CLIENT:
        try:
            sys_inst, contents = _format_messages_for_genai(messages)
            
            config = None
            if sys_inst:
                config = types.GenerateContentConfig(system_instruction=sys_inst)
            
            if contents:
                response = _GEMINI_CLIENT.models.generate_content_stream(
                    model=GEMINI_MODEL_NAME,
                    contents=contents,
                    config=config
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
            print(f" [ZEUS] Erro no Gemini Stream: {e}")

    if DISABLE_OLLAMA:
        yield "Error: Gemini stream unavailable and ZEUS_DISABLE_OLLAMA=1."
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
                    relevant_data.append(f"--- MEMÓRIA SEMÂNTICA (RAG) ---\n{rag_context}\n------------------------------")
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
        system_prompt = "Você é o STRATEGIST do ZEUS. Sua função é analisar o contexto e criar um plano de ação técnico, direto e estratégico. Retorne apenas o plano."
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
        blacklist = ["rm -rf /", "rm -rf *", "mkfs", "dd if=", "chmod 777", "chown -R root"]
        cmd_lower = commands.lower()
        for bad_cmd in blacklist:
            if bad_cmd in cmd_lower:
                return False
        return True

    def execute(self, blackboard):
        system_prompt = (
            "Você é o OPERATOR do ZEUS. Transforme o plano estratégico em comandos de "
            "terminal (Linux/Bash) precisos, mas não os execute. Deixe explícito que a "
            "saída é uma proposta técnica em modo DRY-RUN. "
            "REGRA CRÍTICA DE SEGURANÇA: NUNCA proponha comandos destrutivos (como rm -rf, "
            "formatações ou mudanças globais de permissões). Priorize comandos seguros e de "
            "leitura ou modificação isolada."
        )
        user_prompt = f"Plano: {blackboard.get('plan')}"

        commands = self._call_llm(system_prompt, user_prompt)
        
        is_safe = self._validate_commands(commands)
        mode = "DRY_RUN" if is_safe else "BLOCKED"
        if not is_safe:
            commands = "[OPERAÇÃO BLOQUEADA] A proposta continha comandos na blacklist de segurança.\n" + commands

        result = {
            "mode": mode,
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
            "Você é o CRITIC do ZEUS. Analise a proposta gerada em modo DRY-RUN e "
            "determine se ela parece suficiente e segura para atingir o objetivo. "
            "Responda com 'SUCCESS' ou 'FAILED' seguido da justificativa."
        )
        execution_result = blackboard.get("execution_result")
        serialized_result = json.dumps(execution_result, ensure_ascii=False, indent=2)
        user_prompt = (
            f"Plano original: {blackboard.get('plan')}\n"
            f"Proposta técnica: {serialized_result}"
        )

        metric = self._call_llm(system_prompt, user_prompt)
        status = "SUCCESS" if "SUCCESS" in metric.upper() else "FAILED"
        blackboard.update("status", status)
        blackboard.update("metrics", metric)
        return metric
