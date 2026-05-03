def decide_action(payload: dict) -> dict:
    """
    Decide o destino do conteúdo com base nas tags extraídas.
    Entrada: payload do Obsidian (title, content, tags, path)
    """
    tags = payload.get("tags", [])
    
    action = "memory_only"
    reason = "Sem tags de roteamento detectadas."
    priority = "low"
    labels = []
    
    # Normaliza tags
    tags_lower = [t.lower() for t in tags]
    
    send_to_notion = False
    create_linear_issue = False
    
    # Verifica destinos baseados em tags
    if "#to-notion" in tags_lower or "#project" in tags_lower:
        send_to_notion = True
        
    if "#to-linear" in tags_lower or "#bug" in tags_lower:
        create_linear_issue = True
        
    # Define ação combinada
    if send_to_notion and create_linear_issue:
        action = "both"
        reason = "Tags de Notion e Linear detectadas simultaneamente."
    elif send_to_notion:
        action = "send_to_notion"
        reason = "Tag #to-notion ou #project detectada."
    elif create_linear_issue:
        action = "create_linear_issue"
        reason = "Tag #to-linear ou #bug detectada."
        
    # Extrai labels para Linear
    if "#backend" in tags_lower: labels.append("backend")
    if "#frontend" in tags_lower: labels.append("frontend")
    if "#security" in tags_lower: labels.append("security")
    if "#performance" in tags_lower: labels.append("performance")
    if "#infra" in tags_lower: labels.append("infra")
        
    # Define prioridade
    if "#bug" in tags_lower and "#security" in tags_lower:
        priority = "high"
    elif "#bug" in tags_lower:
        priority = "medium"
    elif "#performance" in tags_lower:
        priority = "medium"
    elif "#project" in tags_lower:
        priority = "medium"
    elif "#idea" in tags_lower:
        priority = "low"
        
    return {
        "action": action,
        "reason": reason,
        "priority": priority,
        "labels": labels,
        "should_use_llm": True if action != "memory_only" else False
    }
