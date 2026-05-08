import os
import shutil
import uuid
from typing import List
from zeus_core.observability import get_logger

logger = get_logger("zeus.self_improvement.rollback")

class RollbackManager:
    def __init__(self):
        self.backup_dir = os.path.join(os.getenv("ZEUS_VAULT_PATH", "."), "backups", "self_improvement")
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, file_paths: List[str]) -> str:
        """Cria um backup dos arquivos e retorna um backup_id."""
        backup_id = uuid.uuid4().hex[:8]
        target_dir = os.path.join(self.backup_dir, backup_id)
        os.makedirs(target_dir, exist_ok=True)
        
        for path in file_paths:
            if os.path.exists(path):
                # Mantém a estrutura de diretórios no backup
                rel_path = os.path.relpath(path, start=os.getcwd())
                dest = os.path.join(target_dir, rel_path)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(path, dest)
                logger.info(f"Backup created: {path} -> {dest}")
        
        return backup_id

    def restore_backup(self, backup_id: str):
        """Restaura os arquivos do backup."""
        target_dir = os.path.join(self.backup_dir, backup_id)
        if not os.path.exists(target_dir):
            logger.error(f"Backup ID {backup_id} not found.")
            return False
            
        for root, _, files in os.walk(target_dir):
            for file in files:
                backup_path = os.path.join(root, file)
                rel_path = os.path.relpath(backup_path, start=target_dir)
                orig_path = os.path.join(os.getcwd(), rel_path)
                
                os.makedirs(os.path.dirname(orig_path), exist_ok=True)
                shutil.copy2(backup_path, orig_path)
                logger.warning(f"Restored file: {orig_path}")
                
        return True

rollback_manager = RollbackManager()
