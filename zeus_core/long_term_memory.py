from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from zeus_core.core_system import call_cloud_llm


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


MEMORY_PATH = _project_root() / "memory" / "long_term.json"
_LOCK = Lock()


def _empty_memory() -> dict:
    return {
        "identity": {},
        "preferences": {},
        "projects": {},
        "relationships": {},
        "wishes": {},
        "notes": {},
    }


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return _empty_memory()
    with _LOCK:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for k in base:
                    if k not in data or not isinstance(data.get(k), dict):
                        data[k] = {}
                return data
        except Exception:
            pass
    return _empty_memory()


def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        MEMORY_PATH.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def _truncate(val: str, max_len: int = 400) -> str:
    if isinstance(val, str) and len(val) > max_len:
        return val[:max_len].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False
    for key, value in (updates or {}).items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue

        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            if isinstance(value, dict) and "value" in value:
                new_val = _truncate(str(value["value"]))
            else:
                new_val = _truncate(str(value))
            entry = {"value": new_val, "updated": datetime.now().strftime("%Y-%m-%d")}
            existing = target.get(key)
            existing_val = existing.get("value") if isinstance(existing, dict) else None
            if existing_val != new_val:
                target[key] = entry
                changed = True
    return changed


def update_memory(memory_update: dict) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()
    memory = load_memory()
    if _recursive_update(memory, memory_update):
        save_memory(memory)
    return memory


def format_memory_for_prompt(memory: Optional[dict]) -> str:
    if not memory:
        return ""
    lines = []
    identity = memory.get("identity", {})
    if isinstance(identity, dict) and identity:
        lines.append("Identity:")
        for k, v in list(identity.items())[:10]:
            val = v.get("value") if isinstance(v, dict) else v
            if val:
                lines.append(f"- {k}: {val}")
        lines.append("")

    for section, label, limit in [
        ("preferences", "Preferences", 12),
        ("projects", "Projects", 10),
        ("relationships", "Relationships", 10),
        ("wishes", "Wishes", 8),
        ("notes", "Notes", 12),
    ]:
        block = memory.get(section, {})
        if isinstance(block, dict) and block:
            lines.append(f"{label}:")
            for k, v in list(block.items())[:limit]:
                val = v.get("value") if isinstance(v, dict) else v
                if val:
                    lines.append(f"- {k}: {val}")
            lines.append("")

    out = "\n".join(lines).strip()
    return out


def should_extract_memory(user_text: str, assistant_text: str) -> bool:
    u = (user_text or "").strip()
    a = (assistant_text or "").strip()
    if len(u) < 5:
        return False

    system = (
        "Você decide se uma conversa contém algo para memória de longo prazo.\n"
        "Responda APENAS 'YES' ou 'NO'.\n"
        "Salve se houver: fatos pessoais, preferências, projetos, pessoas, planos, rotinas.\n"
        "Ignore: resultados de busca, clima, comandos pontuais, logs."
    )
    prompt = f"User: {u[:350]}\nAssistant: {a[:250]}"
    out = call_cloud_llm([{"role": "system", "content": system}, {"role": "user", "content": prompt}])
    return "YES" in (out or "").upper()


def extract_memory(user_text: str, assistant_text: str) -> dict:
    u = (user_text or "").strip()
    a = (assistant_text or "").strip()
    system = (
        "Extraia memória de longo prazo em JSON.\n"
        "Retorne APENAS JSON válido ou {}.\n"
        "Estrutura:\n"
        "{\n"
        "  \"identity\": {\"name\": {\"value\": \"...\"}},\n"
        "  \"preferences\": {...},\n"
        "  \"projects\": {...},\n"
        "  \"relationships\": {...},\n"
        "  \"wishes\": {...},\n"
        "  \"notes\": {...}\n"
        "}\n"
        "Se algo for incerto, não invente."
    )
    prompt = f"User: {u[:600]}\nAssistant: {a[:450]}\n\nJSON:"
    raw = call_cloud_llm([{"role": "system", "content": system}, {"role": "user", "content": prompt}]) or ""
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    if not raw or raw == "{}":
        return {}
    try:
        return json.loads(raw)
    except Exception:
        l = raw.find("{")
        r = raw.rfind("}")
        if l != -1 and r != -1 and r > l:
            try:
                return json.loads(raw[l : r + 1])
            except Exception:
                return {}
        return {}
