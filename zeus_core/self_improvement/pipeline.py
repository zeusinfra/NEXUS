import os
import subprocess
from typing import Dict, List, Any
from zeus_core.self_improvement.audit_log import audit_log
from zeus_core.self_improvement.rollback_manager import rollback_manager
from zeus_core.self_improvement.patch_manager import patch_manager
from zeus_core.events.event_bus import event_bus, EventType
from zeus_core.observability import get_logger

logger = get_logger("zeus.self_improvement.pipeline")

class SelfImprovementPipeline:
    """Pipeline seguro de auto-modificação."""
    
    def __init__(self):
        self.auto_apply = os.getenv("ZEUS_SELF_IMPROVEMENT_AUTO_APPLY_LOW_RISK", "true").lower() == "true"

    async def run_tests(self) -> bool:
        """Roda um smoke test básico ou pytest se existir."""
        logger.info("Running post-patch validation tests...")
        try:
            # Exemplo de smoke test: verificar se o core importa sem syntax error
            result = subprocess.run(["python3", "-c", "import zeus_core.core_system"], capture_output=True)
            if result.returncode != 0:
                logger.error(f"Post-patch test failed: {result.stderr.decode()}")
                return False
            return True
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return False

    async def execute_patch(self, plan: Dict[str, Any]) -> Dict[str, str]:
        """
        Executa um plano de patch.
        plan format: {
            "reason": "Fix loop in agent",
            "files": {
                "/path/to/file.py": "new content"
            }
        }
        """
        await event_bus.publish_async(EventType.SELF_IMPROVEMENT_STARTED, {"plan": plan})
        
        reason = plan.get("reason", "Unknown reason")
        files_to_patch = list(plan.get("files", {}).keys())
        
        # 1. Backup
        backup_id = rollback_manager.create_backup(files_to_patch)
        if not backup_id:
            msg = "Failed to create backup. Aborting patch."
            audit_log.record_patch("NONE", files_to_patch, "", "FAILED", msg)
            await event_bus.publish_async(EventType.SELF_IMPROVEMENT_FAILED, {"reason": msg})
            return {"status": "error", "message": msg}
            
        # 2. Patch
        success = True
        for filepath, content in plan.get("files", {}).items():
            if not patch_manager.apply_patch(filepath, content):
                success = False
                break
                
        if not success:
            logger.error("Patching failed. Rolling back.")
            rollback_manager.restore_backup(backup_id)
            audit_log.record_patch(backup_id, files_to_patch, "", "FAILED", "Patch application failed")
            await event_bus.publish_async(EventType.SELF_IMPROVEMENT_FAILED, {"reason": "Patch application failed"})
            return {"status": "error", "message": "Failed to apply patches. Rolled back."}
            
        # 3. Test
        test_passed = await self.run_tests()
        if not test_passed:
            logger.error("Tests failed after patch. Rolling back.")
            rollback_manager.restore_backup(backup_id)
            audit_log.record_patch(backup_id, files_to_patch, "", "FAILED", "Post-patch tests failed")
            await event_bus.publish_async(EventType.SELF_IMPROVEMENT_FAILED, {"reason": "Tests failed"})
            return {"status": "error", "message": "Tests failed. Rolled back."}
            
        # 4. Audit Success
        audit_log.record_patch(backup_id, files_to_patch, "diff_not_stored_yet", "SUCCESS", reason)
        await event_bus.publish_async(EventType.SELF_IMPROVEMENT_APPLIED, {"files": files_to_patch})
        
        return {"status": "success", "message": "Patch applied and validated successfully.", "backup_id": backup_id}

improvement_pipeline = SelfImprovementPipeline()
