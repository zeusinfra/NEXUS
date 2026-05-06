import os
import requests
from dotenv import load_dotenv

from zeus_core.security.privacy_guard import PrivacyGuard

load_dotenv()

privacy_guard = PrivacyGuard()

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID")
LINEAR_ENABLED = os.getenv("ZEUS_ENABLE_LINEAR", "false").lower() in {"1", "true", "yes", "on"}
GRAPHQL_URL = "https://api.linear.app/graphql"

def _get_headers():
    return {
        "Authorization": LINEAR_API_KEY,
        "Content-Type": "application/json"
    }

def _map_priority(priority_str: str) -> int:
    mapping = {
        "urgent": 1,
        "high": 2,
        "medium": 3,
        "low": 4
    }
    return mapping.get(priority_str.lower(), 0)

def create_linear_issue(title: str, description: str, labels: list[str], priority: str, source_path: str) -> dict:
    if not LINEAR_ENABLED:
        print("[Linear] Integração desabilitada. Ignorando sincronização.")
        return {"error": "Disabled"}
    if not LINEAR_API_KEY or not LINEAR_TEAM_ID:
        print("[Linear] Configuração ausente. Ignorando sincronização.")
        return {"error": "Not configured"}

    # Adiciona link do Obsidian no final da descrição
    full_description = f"{description}\n\n---\n*Origem: {source_path}*"

    # Privacy Check
    validation = privacy_guard.validate_export(f"{title}\n{full_description}", "linear")
    if not validation.allowed:
        print(f"[Linear] Exportação bloqueada por privacidade: {validation.reason}")
        return {"error": "Privacy Block", "reason": validation.reason}
    
    final_desc = validation.sanitized_content if validation.action == "sanitized" else full_description

    mutation = """
    mutation IssueCreate($teamId: String!, $title: String!, $description: String, $priority: Int) {
      issueCreate(input: {
        teamId: $teamId,
        title: $title,
        description: $description,
        priority: $priority
      }) {
        success
        issue {
          id
          identifier
          url
        }
      }
    }
    """
    
    variables = {
        "teamId": LINEAR_TEAM_ID,
        "title": title,
        "description": final_desc,
        "priority": _map_priority(priority)
    }
    
    payload = {
        "query": mutation,
        "variables": variables
    }

    try:
        response = requests.post(GRAPHQL_URL, headers=_get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            print(f"[Linear] GraphQL Error: {data['errors']}")
            return {"error": data['errors']}
            
        issue_data = data.get("data", {}).get("issueCreate", {}).get("issue", {})
        
        # A atribuição de Labels nativamente no Linear requer os IDs dos Labels (LabelCreate/IssueUpdate).
        # Para simplificar na Fase 4, incluímos os labels visuais no texto ou lidamos com IDs cacheados.
        if labels:
            print(f"[Linear] Lembrete: Labels {labels} não foram aplicadas nativamente (requer Label IDs).")
            
        return issue_data
    except requests.exceptions.RequestException as e:
        print(f"[Linear] Erro ao criar issue: {e}")
        return {"error": str(e)}

def get_active_issues() -> list[dict]:
    if not LINEAR_ENABLED:
        return []
    if not LINEAR_API_KEY: return []
    
    query = """
    query {
      viewer {
        assignedIssues(filter: { state: { type: { in: ["started", "unstarted"] } } }) {
          nodes {
            id
            identifier
            title
            state { name }
            priority
          }
        }
      }
    }
    """
    try:
        response = requests.post(GRAPHQL_URL, headers=_get_headers(), json={"query": query}, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("viewer", {}).get("assignedIssues", {}).get("nodes", [])
    except Exception as e:
        print(f"[Linear] Erro ao buscar issues: {e}")
        return []

def get_issue_context(issue_id: str) -> dict:
    if not LINEAR_ENABLED:
        return {}
    if not LINEAR_API_KEY: return {}
    
    query = """
    query Issue($id: String!) {
      issue(id: $id) {
        identifier
        title
        description
        state { name }
        assignee { name }
      }
    }
    """
    try:
        response = requests.post(GRAPHQL_URL, headers=_get_headers(), json={"query": query, "variables": {"id": issue_id}}, timeout=10)
        response.raise_for_status()
        return response.json().get("data", {}).get("issue", {})
    except Exception as e:
        print(f"[Linear] Erro ao buscar contexto da issue: {e}")
        return {}


def create_insight_issue(title: str, description: str, priority: str = "medium", source: str = "zeus-sync-engine") -> dict:
    """
    Wrapper simplificado para criação automática de issues a partir de insights do sync engine.
    Adiciona prefixo [ZEUS Insight] e metadata de origem.
    """
    if not LINEAR_ENABLED:
        return {"error": "Disabled"}
    if not LINEAR_API_KEY or not LINEAR_TEAM_ID:
        return {"error": "Not configured"}

    prefixed_title = f"[ZEUS Insight] {title}"
    full_description = (
        f"{description}\n\n"
        f"---\n"
        f"*Gerado automaticamente pelo ZEUS Sync Engine*\n"
        f"*Fonte: {source}*"
    )

    return create_linear_issue(
        title=prefixed_title,
        description=full_description,
        labels=["zeus-insight"],
        priority=priority,
        source_path=source,
    )
