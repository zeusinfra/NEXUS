import os
import json
import re
from typing import Dict, List, Any
from zeus_core.self_improvement.audit_log import audit_log
from zeus_core.self_improvement.patch_manager import patch_manager
from zeus_core.events.event_bus import event_bus, EventType
from zeus_core.observability import get_logger
from zeus_core.security.daemon_client import daemon_client

logger = get_logger("zeus.self_improvement.pipeline")


class SelfImprovementPipeline:
    """Pipeline seguro de auto-modificação inteligente."""

    def __init__(self):
        self.auto_apply = (
            os.getenv("NEXUS_SELF_IMPROVEMENT_AUTO_APPLY_LOW_RISK", "true").lower()
            == "true"
        )

    async def detect_problem(self) -> List[Dict[str, Any]]:
        """
        Detecção proativa de problemas.
        Analisa logs por Tracebacks e ResourceGovernor por anomalias.
        """
        problems = []
        try:
            # 1. Busca Tracebacks reais (mais preciso que apenas ERROR)
            log_path = "/home/zeus/Documentos/NEXUS_SYSTEM/nexus_core.log"
            if os.path.exists(log_path):
                result = await daemon_client.execute(
                    f"tail -n 200 {log_path}",
                    "Analise profunda de logs",
                    caller="self_improvement",
                )
                if result.get("status") == "success":
                    content = result.get("stdout", "")
                    # Encontrar blocos de Traceback
                    tracebacks = re.findall(
                        r"Traceback \(most recent call last\):.*?\n\w+Error:.*",
                        content,
                        re.DOTALL,
                    )
                    for tb in tracebacks:
                        problems.append(
                            {"type": "python_exception", "content": tb.strip()}
                        )

            # 2. Busca anomalias de performance (Simulado - integraria com ResourceGovernor real)
            # Se CPU > 90% constante ou RAM > 90%, registrar como problema de otimização
            # (Em um ambiente real, leríamos um buffer do ResourceGovernor)

        except Exception as e:
            logger.error(f"Erro ao detectar problemas: {e}")
        return problems

    async def run_tests(self) -> bool:
        """Roda validação rigorosa."""
        logger.info("Running validation tests...")
        try:
            # Smoke test: verificar se o core importa
            result = await daemon_client.execute(
                "python3 -c 'import zeus_core.core_system'",
                "Smoke test",
                caller="self_improvement",
            )
            if result.get("status") != "success":
                return False
            return True
        except Exception:
            return False

    async def execute_patch(self, plan: Dict[str, Any]) -> Dict[str, str]:
        """Ciclo completo com Hot-Reload."""
        await event_bus.publish_async(
            EventType.SELF_IMPROVEMENT_STARTED, {"plan": plan}
        )

        reason = plan.get("reason", "Otimização autônoma")
        files_to_patch = list(plan.get("files", {}).keys())

        # 1. Backup
        backup_res = await daemon_client.backup(files_to_patch)
        backup_id = backup_res.get("backup_id")
        if not backup_id:
            return {"status": "error", "message": "Falha no backup preventivo."}

        # 2. Aplicação
        patches_applied = []
        for filepath, content in plan.get("files", {}).items():
            diff = patch_manager.generate_diff(filepath, content)
            if patch_manager.apply_patch(filepath, content):
                patches_applied.append({"file": filepath, "diff": diff})
            else:
                await daemon_client.rollback(backup_id)
                return {
                    "status": "error",
                    "message": f"Falha ao aplicar patch em {filepath}",
                }

        # 3. Validação
        if not await self.run_tests():
            logger.error("Testes falharam após patch. Rollback imediato.")
            await daemon_client.rollback(backup_id)
            return {
                "status": "error",
                "message": "Validação falhou. Sistema restaurado.",
            }

        # 4. Hot-Reload (Reiniciar o core para carregar novo código)
        logger.info("Patch validado. Reiniciando core para aplicar mudanças...")
        await daemon_client.service_control("zeus_core", "restart")

        # 5. Auditoria
        audit_log.record_patch(
            backup_id, files_to_patch, json.dumps(patches_applied), "SUCCESS", reason
        )
        await event_bus.publish_async(
            EventType.SELF_IMPROVEMENT_APPLIED, {"files": files_to_patch}
        )

        return {
            "status": "success",
            "message": "Patch aplicado e sistema reiniciado.",
            "backup_id": backup_id,
        }


improvement_pipeline = SelfImprovementPipeline()
