from zeus_core.integrations.obsidian import write_obsidian_insight, read_note

def tool_write_obsidian_insight(title: str, content: str) -> str:
    """Escreve um insight ou reflexão do ZEUS no Obsidian."""
    try:
        path = write_obsidian_insight(title, content)
        return f"Insight salvo no Obsidian em: {path}"
    except Exception as e:
        return f"Erro ao salvar no Obsidian: {e}"

def tool_read_obsidian_note(path: str) -> str:
    """Lê uma nota específica do Obsidian."""
    try:
        note = read_note(path)
        return f"Título: {note['title']}\nTags: {note['tags']}\nConteúdo:\n{note['content'][:2000]}"
    except Exception as e:
        return f"Erro ao ler nota: {e}"
