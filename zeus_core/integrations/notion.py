import os
import requests
import json

from zeus_core.env import load_project_env
from zeus_core.security.privacy_guard import PrivacyGuard

load_project_env()

privacy_guard = PrivacyGuard()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_ENABLED = os.getenv("ZEUS_ENABLE_NOTION", "false").lower() in {"1", "true", "yes", "on"}
NOTION_VERSION = "2022-06-28"

BASE_URL = "https://api.notion.com/v1"
_DATABASE_PROPERTIES_CACHE = None

def _get_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION
    }


def _get_database_properties() -> dict:
    global _DATABASE_PROPERTIES_CACHE
    if _DATABASE_PROPERTIES_CACHE is not None:
        return _DATABASE_PROPERTIES_CACHE
    if not NOTION_ENABLED or not NOTION_TOKEN or not NOTION_DATABASE_ID:
        _DATABASE_PROPERTIES_CACHE = {}
        return _DATABASE_PROPERTIES_CACHE
    try:
        response = requests.get(f"{BASE_URL}/databases/{NOTION_DATABASE_ID}", headers=_get_headers(), timeout=10)
        response.raise_for_status()
        _DATABASE_PROPERTIES_CACHE = response.json().get("properties", {}) or {}
    except Exception as e:
        print(f"[Notion] Erro ao ler schema do database: {e}")
        _DATABASE_PROPERTIES_CACHE = {}
    return _DATABASE_PROPERTIES_CACHE


def _title_property_name() -> str:
    props = _get_database_properties()
    for name, spec in props.items():
        if (spec or {}).get("type") == "title":
            return name
    return "Name"


def _build_page_properties(title: str, tags: list[str], source_path: str) -> dict:
    props = _get_database_properties()
    title_prop = _title_property_name()
    page_props = {
        title_prop: {
            "title": [
                {
                    "text": {"content": title[:2000]}
                }
            ]
        }
    }

    if props.get("Source Path", {}).get("type") == "rich_text":
        page_props["Source Path"] = {
            "rich_text": [
                {
                    "text": {"content": (source_path or "")[:2000]}
                }
            ]
        }

    if props.get("Tags", {}).get("type") == "multi_select":
        page_props["Tags"] = {
            "multi_select": [{"name": t.replace('#', '')[:100]} for t in tags if t]
        }

    return page_props

def _markdown_to_blocks(content: str) -> list:
    """Conversor simplificado de MD para Notion Blocks. Em prod, usar 'notion-blockify' ou similar."""
    blocks = []
    lines = content.split('\n')
    for line in lines:
        if not line.strip():
            continue
        # Trata tudo como parágrafo (simplificação para a Fase 3)
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": line[:2000] # Limite de chars do Notion por text block
                        }
                    }
                ]
            }
        })
    return blocks

def create_notion_page(title: str, content: str, tags: list[str], source_path: str) -> dict:
    if not NOTION_ENABLED:
        print("[Notion] Integração desabilitada. Ignorando sincronização.")
        return {"error": "Disabled"}
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("[Notion] Configuração ausente. Ignorando sincronização.")
        return {"error": "Not configured"}

    url = f"{BASE_URL}/pages"
    
    # Privacy Check
    validation = privacy_guard.validate_export(f"{title}\n{content}", "notion")
    if not validation.allowed:
        print(f"[Notion] Exportação bloqueada por privacidade: {validation.reason}")
        return {"error": "Privacy Block", "reason": validation.reason}
    
    final_content = validation.sanitized_content if validation.action == "sanitized" else content
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": _build_page_properties(title, tags, source_path),
        "children": _markdown_to_blocks(final_content)
    }

    try:
        response = requests.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Notion] Erro ao criar página: {e}")
        return {"error": str(e)}

def update_notion_page(page_id: str, content: str) -> dict:
    # A atualização de conteúdo no Notion requer deletar blocos antigos e inserir novos (APPEND).
    # Para simplificar, estamos apenas atualizando properties aqui.
    print("[Notion] Atualização de blocos requer lógica complexa (Append/Delete block children). Omitido por enquanto.")
    return {"status": "not_implemented"}

def search_notion(query: str) -> list[dict]:
    if not NOTION_ENABLED:
        return []
    if not NOTION_TOKEN: return []
    
    url = f"{BASE_URL}/search"
    payload = {
        "query": query,
        "sort": {
            "direction": "descending",
            "timestamp": "last_edited_time"
        }
    }
    try:
        response = requests.post(url, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        print(f"[Notion] Erro ao buscar: {e}")
        return []


def upsert_notion_page(title: str, content: str, tags: list[str], source_path: str) -> dict:
    """
    Cria ou atualiza uma página no Notion Database.
    Busca por título existente para evitar duplicatas.
    """
    if not NOTION_ENABLED:
        return {"error": "Disabled"}
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return {"error": "Not configured"}

    # 1. Busca página existente pelo título no database
    search_url = f"{BASE_URL}/databases/{NOTION_DATABASE_ID}/query"
    title_prop = _title_property_name()
    search_payload = {
        "filter": {
            "property": title_prop,
            "title": {
                "equals": title
            }
        },
        "page_size": 1
    }

    existing_page_id = None
    try:
        resp = requests.post(search_url, headers=_get_headers(), json=search_payload, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            existing_page_id = results[0]["id"]
    except Exception as e:
        print(f"[Notion] Erro ao buscar página existente: {e}")

    if existing_page_id:
        # 2a. Atualizar página existente: append de blocos novos
        append_url = f"{BASE_URL}/blocks/{existing_page_id}/children"
        # Adiciona separador visual antes do conteúdo atualizado
        separator_block = {"object": "block", "type": "divider", "divider": {}}
        new_blocks = [separator_block] + _markdown_to_blocks(content)

        try:
            resp = requests.patch(append_url, headers=_get_headers(), json={"children": new_blocks}, timeout=10)
            resp.raise_for_status()
            print(f"[Notion] Página '{title}' atualizada (ID: {existing_page_id})")
            return {"id": existing_page_id, "action": "updated"}
        except Exception as e:
            print(f"[Notion] Erro ao atualizar página: {e}")
            return {"error": str(e)}
    else:
        # 2b. Criar página nova
        result = create_notion_page(title, content, tags, source_path)
        if "id" in result:
            result["action"] = "created"
        return result
