from __future__ import annotations

import json
import re
from typing import Any, Dict

from zeus_core.core_system import call_cloud_llm


PLANNER_PROMPT = """Você é o PLANNER do ZEUS.
Quebre o objetivo do usuário em uma sequência curta de passos usando APENAS as ferramentas listadas.

REGRAS:
- Máximo de 5 passos (use o mínimo necessário).
- Cada passo deve ser independente e autoexplicativo.
- Não escreva código Python gerado. Não invente ferramentas.
- Se precisar manipular arquivos, use file_controller.
- Se precisar rodar um comando, use cmd_control (apenas comandos simples, sem pipes).

FERRAMENTAS:

get_time
  params: {}

file_controller
  action: list | read | write | create_file | create_folder | delete | move | copy | rename | find | disk_usage
  path: caminho relativo ao projeto (ex: "README.md" ou "zeus_core")
  content: texto (para write/create_file)
  destination: destino (move/copy)
  new_name: novo nome (rename)

cmd_control
  command: string (comando a executar)
  timeout_s: int (opcional)

browser_control
  action: "go_to" | "search" | "click" | "type" | "scroll" | "press" | "get_text" | "close"
  url: string (go_to)
  query: string (search)
  selector: string (click/type/get_text)
  text: string (type)
  key: string (press)

screen_process
  text: string (o que você quer saber sobre a tela)
  angle: "screen" (opcional)
  ocr: boolean (opcional; tenta OCR se tesseract existir)

OUTPUT: retorne APENAS JSON válido:
{
  "goal": "...",
  "steps": [
    {"step": 1, "tool": "tool_name", "description": "...", "parameters": {}, "critical": true}
  ]
}
"""


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    if not text:
        raise ValueError("empty")
    try:
        return json.loads(text)
    except Exception:
        l = text.find("{")
        r = text.rfind("}")
        if l != -1 and r != -1 and r > l:
            return json.loads(text[l : r + 1])
        raise


def create_plan(goal: str, *, context: str = "") -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": PLANNER_PROMPT},
        {"role": "user", "content": f"Objetivo: {goal}\n\nContexto:\n{context}" if context else f"Objetivo: {goal}"},
    ]
    raw = call_cloud_llm(messages)
    try:
        plan = _extract_json(raw)
        if not isinstance(plan, dict) or "steps" not in plan:
            raise ValueError("invalid plan")
        if not isinstance(plan.get("steps"), list):
            raise ValueError("invalid steps")
        return plan
    except Exception:
        return {
            "goal": goal,
            "steps": [
                {
                    "step": 1,
                    "tool": "cmd_control",
                    "description": "Inspecionar diretório do projeto",
                    "parameters": {"command": "ls -la"},
                    "critical": True,
                }
            ],
        }


def replan(goal: str, *, completed_steps: list, failed_step: dict, error: str) -> Dict[str, Any]:
    summary = "\n".join([f"- Step {s.get('step')} [{s.get('tool')}]: OK" for s in (completed_steps or [])])
    context = (
        f"Já concluído:\n{summary if summary else '(nada)'}\n\n"
        f"Falha em: {json.dumps(failed_step, ensure_ascii=False)}\n"
        f"Erro: {error}\n"
    )
    return create_plan(goal, context=context)
