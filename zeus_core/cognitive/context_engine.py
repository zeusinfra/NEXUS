from zeus_core.integrations.linear import get_active_issues
from zeus_core.memory.sqlite_memory import get_connection

def _get_recent_notes(limit: int = 3) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT file_path, detected_tags 
        FROM processed_files 
        ORDER BY last_processed_at DESC 
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    notes = []
    for row in rows:
        notes.append({
            "path": row[0],
            "tags": row[1]
        })
    return notes

def build_current_context() -> str:
    """
    Constrói um resumo do contexto atual do usuário para injetar no LLM do agente ZEUS.
    """
    context_lines = ["Contexto atual:"]
    
    # 1. Busca issues ativas no Linear
    issues = get_active_issues()
    if issues:
        context_lines.append("- O usuário está trabalhando nas seguintes issues:")
        for issue in issues:
            title = issue.get('title', 'Sem título')
            state = issue.get('state', {}).get('name', 'N/A')
            context_lines.append(f"  * [{issue.get('identifier')}] {title} (Status: {state})")
    else:
        context_lines.append("- Nenhuma issue ativa no Linear no momento.")
        
    # 2. Busca notas recentes do Obsidian
    recent_notes = _get_recent_notes()
    if recent_notes:
        context_lines.append("- Últimas anotações capturadas do Obsidian:")
        for note in recent_notes:
            context_lines.append(f"  * {note['path']} (Tags: {note['tags']})")
            
    return "\n".join(context_lines)
