import os
import json
import datetime
from zeus_core.observability import get_logger

logger = get_logger("zeus.self_improvement.audit")

class AuditLog:
    def __init__(self):
        self.log_path = os.path.join(os.getenv("ZEUS_VAULT_PATH", "."), "logs", "self_improvement_audit.log")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def record_patch(self, patch_id: str, files_changed: list, diff: str, status: str, reason: str):
        try:
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "patch_id": patch_id,
                "files_changed": files_changed,
                "diff": diff,
                "status": status,
                "reason": reason
            }
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

audit_log = AuditLog()
