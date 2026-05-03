from zeus_core.integrations.notion import create_notion_page, search_notion

def tool_create_notion_page(title: str, content: str, tags: list = None) -> str:
    """Cria uma página estruturada no banco de dados Notion configurado."""
    tags = tags or []
    try:
        resp = create_notion_page(title, content, tags, "ReAct Agent")
        if 'error' in resp:
            return f"Falha ao criar página: {resp['error']}"
        return f"Página criada com sucesso. URL: {resp.get('url', 'N/A')}"
    except Exception as e:
        return f"Erro na integração Notion: {e}"

def tool_search_notion(query: str) -> str:
    """Busca por páginas no Notion correspondentes à query."""
    try:
        results = search_notion(query)
        if not results:
            return "Nenhum resultado encontrado."
        
        output = []
        for r in results[:5]:
            # Parsing complexo evitado, pegamos url
            output.append(f"- URL: {r.get('url')}")
        return "\n".join(output)
    except Exception as e:
        return f"Erro na busca do Notion: {e}"
