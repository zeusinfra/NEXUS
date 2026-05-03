from zeus_core.integrations.linear import create_linear_issue, get_active_issues, get_issue_context

def tool_create_linear_issue(title: str, description: str, labels: list = None, priority: str = "medium") -> str:
    """Cria uma tarefa/issue estruturada no Linear."""
    labels = labels or []
    try:
        resp = create_linear_issue(title, description, labels, priority, "ReAct Agent")
        if 'error' in resp:
            return f"Falha ao criar issue: {resp['error']}"
        return f"Issue criada com sucesso. URL: {resp.get('url', 'N/A')} [{resp.get('identifier', '')}]"
    except Exception as e:
        return f"Erro na integração Linear: {e}"

def tool_get_current_dev_context() -> str:
    """Busca as issues ativas que o usuário está trabalhando no Linear."""
    try:
        issues = get_active_issues()
        if not issues:
            return "Nenhuma issue em andamento."
        
        output = ["Issues ativas:"]
        for issue in issues:
            output.append(f"- [{issue['identifier']}] {issue['title']} (Prioridade: {issue['priority']})")
        return "\n".join(output)
    except Exception as e:
        return f"Erro ao buscar contexto dev: {e}"
