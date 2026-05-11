import os
import difflib
from nexus_core.observability import get_logger

logger = get_logger("zeus.self_improvement.patch")


class PatchManager:
    def __init__(self):
        pass

    def generate_diff(self, file_path: str, new_content: str) -> str:
        """Gera um unified diff do patch."""
        try:
            if not os.path.exists(file_path):
                return f"New file: {file_path}"

            with open(file_path, "r", encoding="utf-8") as f:
                old_content = f.read()

            diff = difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="a/" + file_path,
                tofile="b/" + file_path,
            )
            return "".join(diff)
        except Exception as e:
            logger.error(f"Failed to generate diff for {file_path}: {e}")
            return ""

    def apply_patch(self, file_path: str, new_content: str) -> bool:
        """Aplica o novo conteúdo ao arquivo. Assume que o backup já foi feito."""
        try:
            # Validação de syntax básica para Python
            if file_path.endswith(".py"):
                try:
                    compile(new_content, file_path, "exec")
                except SyntaxError as se:
                    logger.error(
                        f"Syntax error in proposed patch for {file_path}: {se}"
                    )
                    return False

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"Patch applied successfully to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to apply patch to {file_path}: {e}")
            return False


patch_manager = PatchManager()
