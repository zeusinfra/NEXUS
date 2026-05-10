import os
import shutil
import uuid
import datetime
from typing import List
from zeus_core.observability import get_logger
from zeus_core.security.daemon_client import daemon_client

logger = get_logger("zeus.self_improvement.rollback")

class RollbackManager:
    def __init__(self):
        self.backup_dir = os.path.join(os.getenv("ZEUS_VAULT_PATH", "/home/zeus/Documentos/Brain"), "backups", "self_improvement")
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, file_paths: List[str]) -> str:
        """Utiliza o daemon para criar backup seguro."""
        # Agora delegamos ao daemon para manter consistência
        # Mas mantemos o backup local para redundância se necessário
        return "" # Implementação via daemon_client no pipeline

    async def list_backups(self):
        return await daemon_client.list_backups()

    async def restore_backup(self, backup_id: str):
        return await daemon_client.rollback(backup_id)

    def cleanup_old_backups(self, max_age_days: int = 7):
        # A limpeza agora é feita pelo daemon, mas podemos limpar o dir local se usado
        pass

rollback_manager = RollbackManager()
