import asyncio

from nexus_core.events.event_bus import get_pending_events, mark_event_processed
from nexus_core.cognitive.classifier import decide_action
from nexus_core.integrations.notion import create_notion_page
from nexus_core.integrations.linear import create_linear_issue
from nexus_core.memory.sqlite_memory import link_external_resource


async def sync_worker_loop(poll_interval: float = 3.0):
    """
    Loop assíncrono para processar eventos pendentes da fila SQLite.
    Garante resiliência e que nenhum evento seja perdido se os serviços caírem.
    """
    print("[SyncWorker] Iniciando background worker para eventos...")

    while True:
        try:
            events = get_pending_events(limit=5)
            for event in events:
                await _process_event(event)
        except Exception as e:
            print(f"[SyncWorker] Erro crítico no loop de eventos: {e}")

        await asyncio.sleep(poll_interval)


async def _process_event(event: dict):
    """Processa individualmente um evento e marca como resolvido."""
    event_id = event["id"]
    payload = event["payload"]

    print(
        f"[SyncWorker] Processando evento ID {event_id}: {payload.get('title', 'Sem titulo')}"
    )

    try:
        # Chama o classificador
        decision = decide_action(payload)
        action = decision.get("action")

        print(
            f"[SyncWorker] Decisão para '{payload.get('title')}': {action} ({decision.get('reason')})"
        )

        if action in ["send_to_notion", "both"]:
            print("[SyncWorker] Enviando para Notion...")
            notion_resp = create_notion_page(
                title=payload.get("title"),
                content=payload.get("content"),
                tags=payload.get("tags"),
                source_path=payload.get("path"),
            )
            if "id" in notion_resp:
                link_external_resource(
                    obsidian_path=payload.get("path"), notion_id=notion_resp["id"]
                )

        if action in ["create_linear_issue", "both"]:
            print("[SyncWorker] Enviando para Linear...")
            linear_resp = create_linear_issue(
                title=payload.get("title"),
                description=payload.get("content")[:5000],  # Limite seguro
                labels=decision.get("labels", []),
                priority=decision.get("priority", "medium"),
                source_path=payload.get("path"),
            )
            if "id" in linear_resp:
                link_external_resource(
                    obsidian_path=payload.get("path"), linear_id=linear_resp["id"]
                )

        # Registramos sucesso no DB
        mark_event_processed(event_id, status="processed")

    except Exception as e:
        print(f"[SyncWorker] Erro ao processar evento {event_id}: {e}")
        mark_event_processed(event_id, status="error", error_message=str(e))
