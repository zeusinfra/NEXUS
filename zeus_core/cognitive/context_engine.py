from zeus_core.integrations.linear import get_active_issues
from zeus_core.memory.sqlite_memory import get_connection, get_sync_status
import time

_ISSUES_CACHE = {"ts": 0.0, "items": []}
_ISSUES_CACHE_TTL_SECONDS = 90.0


def _get_recent_notes(limit: int = 3) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT file_path, detected_tags 
        FROM processed_files 
        ORDER BY last_processed_at DESC 
        LIMIT ?
    """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    notes = []
    for row in rows:
        notes.append({"path": row[0], "tags": row[1]})
    return notes


def _get_cached_issues() -> list[dict]:
    now = time.time()
    if now - float(_ISSUES_CACHE["ts"]) < _ISSUES_CACHE_TTL_SECONDS:
        return list(_ISSUES_CACHE["items"])
    issues = get_active_issues()
    _ISSUES_CACHE["ts"] = now
    _ISSUES_CACHE["items"] = list(issues or [])
    return list(_ISSUES_CACHE["items"])


def _area_from_tags(tags: str | None) -> str:
    t = (tags or "").lower()
    if "to-linear" in t or "bug" in t or "infra" in t or "performance" in t:
        return "tarefa/operação"
    if "to-notion" in t or "project" in t or "docs" in t:
        return "documentação"
    if "zeus" in t or "memory" in t:
        return "memória"
    return "memória local"


def build_current_context() -> str:
    """
    Constrói um resumo do contexto atual do usuário para injetar no LLM do agente ZEUS.
    """
    context_lines = ["Contexto operacional atual:"]

    sync_status = get_sync_status()
    context_lines.append(
        f"- Sincronização: pendentes={sync_status.get('pending', 0)}, processados={sync_status.get('processed', 0)}, erros={sync_status.get('error', 0)}."
    )

    # 1. Busca issues ativas no Linear com cache curto para reduzir latência
    issues = _get_cached_issues()
    if issues:
        context_lines.append("- Tarefas Linear ativas:")
        for issue in issues:
            title = issue.get("title", "Sem título")
            state = issue.get("state", {}).get("name", "N/A")
            context_lines.append(
                f"  * [tarefa] [{issue.get('identifier')}] {title} (status: {state})"
            )
    else:
        context_lines.append("- Tarefas Linear: nenhuma issue ativa carregada.")

    # 2. Busca notas recentes do Obsidian
    recent_notes = _get_recent_notes()
    if recent_notes:
        context_lines.append("- Memórias/Notas Obsidian recentes:")
        for note in recent_notes:
            area = _area_from_tags(note.get("tags"))
            context_lines.append(f"  * [{area}] {note['path']} (tags: {note['tags']})")

    return "\n".join(context_lines)
