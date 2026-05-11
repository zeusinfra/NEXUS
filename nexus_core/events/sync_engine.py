"""
ZEUS Sync Engine — Real-Time Memory Synchronization

Orchestrates 3 independent async workers:
1. Synaptic Memory → Obsidian (every 60s)
2. Long-Term Memory → Notion (every 5min)
3. Anomaly Detection → Linear (every 5min)
"""

import asyncio
import os
from datetime import datetime

from nexus_core.integrations.obsidian import write_sync_note, update_daily_log
from nexus_core.integrations.notion import upsert_notion_page
from nexus_core.integrations.linear import create_insight_issue
from nexus_core.memory.sqlite_memory import (
    get_sync_status,
    log_sync_event,
    was_already_synced,
)
from nexus_core.long_term_memory import load_memory as load_long_term_memory


# ---------- Worker 1: Synaptic → Obsidian ----------


async def sync_synaptic_to_obsidian(memory_manager, interval: float = 60.0):
    """
    Periodically exports synaptic memory snapshot to Obsidian markdown notes.
    Creates: NEXUS_Sync/Synaptic/neural_map.md, NEXUS_Sync/Patterns/*.md, NEXUS_Sync/Daily/*.md
    """
    print("[SyncEngine] Worker Sináptico→Obsidian iniciado.")

    while True:
        try:
            snapshot = memory_manager.export_sync_snapshot()

            if snapshot["total_nodes"] == 0:
                await asyncio.sleep(interval)
                continue

            # 1. Neural Map
            neural_map_content = _format_neural_map(snapshot)
            write_sync_note("Synaptic", "neural_map", neural_map_content)

            # 2. Daily Log entry
            daily_entries = []
            daily_entries.append(
                f"**Nós ativos:** {snapshot['total_nodes']} | **Sinapses:** {snapshot['total_synapses']} | **Buffer sensorial:** {snapshot['sensory_buffer_size']}"
            )

            if snapshot["top_nodes"]:
                top = snapshot["top_nodes"][0]
                daily_entries.append(
                    f"**Foco principal:** `{os.path.basename(top['path'])}` (peso {top['weight']})"
                )

            if snapshot["recent_patterns"]:
                pattern = snapshot["recent_patterns"][0]
                daily_entries.append(
                    f"**Último padrão:** {pattern['type']} — {pattern.get('context', 'N/A')}"
                )

            update_daily_log(daily_entries)

            log_sync_event(
                source="synaptic_memory",
                target="obsidian",
                source_path="memory_manager.export_sync_snapshot",
                target_id="NEXUS_Sync/Synaptic/neural_map.md",
                status="success",
            )

        except Exception as e:
            print(f"[SyncEngine] Erro no sync Sináptico→Obsidian: {e}")
            try:
                log_sync_event(
                    source="synaptic_memory",
                    target="obsidian",
                    source_path="memory_manager",
                    status="error",
                    error_message=str(e),
                )
            except Exception:
                pass

        await asyncio.sleep(interval)


# ---------- Worker 2: Long-Term → Notion ----------


async def sync_longterm_to_notion(interval: float = 300.0):
    """
    Periodically syncs long-term memory (identity, preferences, projects) to Notion.
    Uses upsert to avoid duplicating pages.
    """
    print("[SyncEngine] Worker LongTerm→Notion iniciado.")

    while True:
        try:
            memory = load_long_term_memory()

            # Sync profile when long-term memory exists; otherwise publish an operational status page
            # so the Notion workspace receives visible ZEUS data immediately.
            has_content = any(
                isinstance(memory.get(section), dict) and memory[section]
                for section in [
                    "identity",
                    "preferences",
                    "projects",
                    "relationships",
                    "wishes",
                    "notes",
                ]
            )

            if has_content:
                title = "ZEUS — Perfil Cognitivo"
                content = _format_memory_for_notion(memory)
                tags = ["zeus-memory", "auto-sync", "cognitive-profile"]
                source_path = "long_term_memory.json"
            else:
                title = "ZEUS — Estado Operacional"
                content = _format_operational_status_for_notion(get_sync_status())
                tags = ["zeus-memory", "auto-sync", "operational-status"]
                source_path = "zeus_events.db"

            result = await asyncio.to_thread(
                upsert_notion_page,
                title=title,
                content=content,
                tags=tags,
                source_path=source_path,
            )

            if "id" in result:
                log_sync_event(
                    source="long_term_memory" if has_content else "operational_status",
                    target="notion",
                    source_path=source_path,
                    target_id=result["id"],
                    status="success",
                )
                action = result.get("action", "synced")
                print(f"[SyncEngine] {title} {action} no Notion (ID: {result['id']})")
            elif "error" in result and result["error"] not in (
                "Disabled",
                "Not configured",
            ):
                log_sync_event(
                    source="long_term_memory" if has_content else "operational_status",
                    target="notion",
                    source_path=source_path,
                    status="error",
                    error_message=str(result["error"]),
                )

        except Exception as e:
            print(f"[SyncEngine] Erro no sync LongTerm→Notion: {e}")
            try:
                log_sync_event(
                    source="long_term_memory",
                    target="notion",
                    source_path="memory/long_term.json",
                    status="error",
                    error_message=str(e),
                )
            except Exception:
                pass

        await asyncio.sleep(interval)


# ---------- Worker 3: Anomalies → Linear ----------


async def sync_insights_to_linear(memory_manager, interval: float = 300.0):
    """
    Periodically checks for synaptic anomalies and creates Linear issues.
    Deduplicates by checking sync_logs before creating.
    """
    print("[SyncEngine] Worker Insights→Linear iniciado.")

    while True:
        try:
            anomalies = memory_manager.get_anomalies()

            for anomaly in anomalies:
                # Build a unique dedup key from the anomaly
                dedup_key = f"anomaly:{anomaly['type']}:{anomaly.get('path', anomaly.get('source', 'unknown'))}"

                if was_already_synced(
                    source="anomaly_detector", target="linear", source_path=dedup_key
                ):
                    continue

                result = await asyncio.to_thread(
                    create_insight_issue,
                    title=anomaly["title"],
                    description=anomaly["description"],
                    priority=anomaly.get("priority", "medium"),
                    source=dedup_key,
                )

                if isinstance(result, dict) and result.get("id"):
                    log_sync_event(
                        source="anomaly_detector",
                        target="linear",
                        source_path=dedup_key,
                        target_id=result.get("identifier", result.get("id")),
                        status="success",
                    )
                    print(f"[SyncEngine] Issue criada no Linear: {anomaly['title']}")
                elif isinstance(result, dict) and result.get("error") not in (
                    "Disabled",
                    "Not configured",
                ):
                    log_sync_event(
                        source="anomaly_detector",
                        target="linear",
                        source_path=dedup_key,
                        status="error",
                        error_message=str(result.get("error")),
                    )

        except Exception as e:
            print(f"[SyncEngine] Erro no sync Insights→Linear: {e}")

        await asyncio.sleep(interval)


# ---------- Formatters ----------


def _format_neural_map(snapshot: dict) -> str:
    """Formats a synaptic snapshot into a readable Obsidian markdown note."""
    lines = [
        f"# Mapa Neural ZEUS",
        f"",
        f"> Snapshot gerado em {snapshot['timestamp']}",
        f"",
        f"## Resumo",
        f"",
        f"| Métrica | Valor |",
        f"|---|---|",
        f"| Nós totais | {snapshot['total_nodes']} |",
        f"| Sinapses totais | {snapshot['total_synapses']} |",
        f"| Buffer sensorial | {snapshot['sensory_buffer_size']} |",
        f"",
        f"## Top Nós (por peso)",
        f"",
        f"| Caminho | Peso | Último Acesso |",
        f"|---|---|---|",
    ]

    for node in snapshot["top_nodes"]:
        basename = os.path.basename(node["path"])
        lines.append(
            f"| `{basename}` | {node['weight']} | {node.get('last_accessed', 'N/A')} |"
        )

    lines.extend(
        [
            f"",
            f"## Sinapses Mais Fortes",
            f"",
            f"| Origem | Destino | Peso |",
            f"|---|---|---|",
        ]
    )

    for syn in snapshot["top_synapses"]:
        src = os.path.basename(syn["source"])
        tgt = os.path.basename(syn["target"])
        lines.append(f"| `{src}` | `{tgt}` | {syn['weight']} |")

    if snapshot["recent_patterns"]:
        lines.extend(
            [
                f"",
                f"## Padrões Recentes",
                f"",
            ]
        )
        for pat in snapshot["recent_patterns"]:
            lines.append(
                f"- **{pat['type']}**: {pat.get('context', 'N/A')} (importância: {pat.get('importance', 'N/A')})"
            )

    return "\n".join(lines)


def _format_memory_for_notion(memory: dict) -> str:
    """Formats long-term memory into structured text for Notion page content."""
    lines = [
        f"# ZEUS — Perfil Cognitivo",
        f"",
        f"> Última sincronização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
    ]

    section_labels = {
        "identity": "🧬 Identidade",
        "preferences": "⚙️ Preferências",
        "projects": "📋 Projetos",
        "relationships": "👥 Relações",
        "wishes": "🎯 Desejos",
        "notes": "📝 Notas",
    }

    for section, label in section_labels.items():
        block = memory.get(section, {})
        if not isinstance(block, dict) or not block:
            continue

        lines.append(f"## {label}")
        lines.append("")

        for key, value in list(block.items())[:15]:
            val = value.get("value") if isinstance(value, dict) else value
            updated = value.get("updated", "") if isinstance(value, dict) else ""
            if val:
                date_suffix = f" _(atualizado: {updated})_" if updated else ""
                lines.append(f"- **{key}**: {val}{date_suffix}")

        lines.append("")

    return "\n".join(lines)


def _format_operational_status_for_notion(sync_status: dict) -> str:
    """Formats a minimal operational status page for Notion when long-term memory is empty."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "\n".join(
        [
            "# ZEUS — Estado Operacional",
            "",
            f"> Última sincronização: {generated_at}",
            "",
            "## Second Brain",
            "",
            f"- Eventos totais: {sync_status.get('total_events', 0)}",
            f"- Eventos pendentes: {sync_status.get('pending', 0)}",
            f"- Eventos processados: {sync_status.get('processed', 0)}",
            f"- Eventos com erro: {sync_status.get('error', 0)}",
            f"- Operações de sync registradas: {sync_status.get('total_sync_ops', 0)}",
            f"- Última operação de sync: {sync_status.get('last_sync_op') or 'N/A'}",
            "",
            "## Observação",
            "",
            "A memória longa ainda não possui perfil cognitivo persistido. Esta página confirma que o ZEUS já está conectado ao Notion e pronto para sincronizar dados conforme a memória for sendo construída.",
        ]
    )
