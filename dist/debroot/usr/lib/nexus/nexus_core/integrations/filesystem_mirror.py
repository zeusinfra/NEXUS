import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from nexus_core.path_filters import is_runtime_noise_path
from nexus_core.memory_manager import MemoryManager


class FilesystemMirror:
    """
    NEXUS Filesystem Mirror
    Maps OS directories and files into Obsidian markdown notes with hierarchical and synaptic links.
    """

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager
        self.vault_path = os.getenv(
            "NEXUS_VAULT_PATH", str(Path.home() / "Documentos" / "Brain")
        )
        self.mirror_root = os.path.join(self.vault_path, "OS_Mirror")
        os.makedirs(self.mirror_root, exist_ok=True)

    def mirror_path(self, root_path: str, max_depth: int = 3) -> str:
        """
        Recursively mirrors a path into the Obsidian vault.
        """
        root = Path(root_path).resolve()
        if not root.exists():
            return f"Erro: Caminho não encontrado: {root_path}"

        count = self._process_node(root, depth=0, max_depth=max_depth)
        return f"Espelhamento concluído. {count} itens mapeados em {self.mirror_root}."

    def _process_node(self, current_path: Path, depth: int, max_depth: int) -> int:
        """Processes a single node (file or directory)."""
        if is_runtime_noise_path(current_path):
            return 0

        if current_path.is_dir():
            if depth > max_depth:
                return 0

            self._create_folder_note(current_path)
            processed_count = 1

            try:
                for item in current_path.iterdir():
                    processed_count += self._process_node(item, depth + 1, max_depth)
            except PermissionError:
                pass
            return processed_count
        else:
            if depth > max_depth:
                return 0
            self._create_file_note(current_path)
            return 1

    def _get_mirror_file_path(self, original_path: Path) -> str:
        """Translates an absolute path to a structured Obsidian path."""
        # Se for a raiz, usamos um nome especial
        if str(original_path) == "/":
            return os.path.join(self.mirror_root, "root.md")

        # Remove a barra inicial para construir o caminho relativo dentro do mirror_root
        rel_path = str(original_path).lstrip("/")

        if original_path.is_dir():
            # Para diretórios, criamos uma pasta e uma nota com o mesmo nome dentro dela (padrão Folder Note)
            return os.path.join(self.mirror_root, rel_path, f"{original_path.name}.md")
        else:
            # Para arquivos, mantemos a estrutura de pastas e adicionamos .md
            return os.path.join(self.mirror_root, rel_path + ".md")

    def _create_folder_note(self, path: Path):
        """Generates a note for a directory."""
        mirror_path = self._get_mirror_file_path(path)
        os.makedirs(os.path.dirname(mirror_path), exist_ok=True)

        children = []
        try:
            for item in path.iterdir():
                if not is_runtime_noise_path(item):
                    children.append(item)
        except PermissionError:
            pass

        content = [
            f"# Diretório: {path.name}",
            "",
            f"**Caminho Original:** `{path}`",
            f"**Tipo:** `Directory`",
            f"**Data de Mapeamento:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Conteúdo",
            "",
        ]

        # Parent link
        if path.parent and path.parent != path:
            parent_mirror = Path(self._get_mirror_file_path(path.parent)).stem
            content.append(f"- **Parent:** [[{parent_mirror}|⬆️ ..]]")

        # Sub-items
        for child in sorted(children, key=lambda x: (not x.is_dir(), x.name)):
            child_mirror = Path(self._get_mirror_file_path(child)).stem
            emoji = "📁" if child.is_dir() else "📄"
            content.append(f"- {emoji} [[{child_mirror}|{child.name}]]")

        # Synaptic Context
        if self.memory_manager:
            weight = self._get_synaptic_weight(str(path))
            if weight > 1:
                content.append("")
                content.append("## Inteligência NEXUS")
                content.append(f"- **Peso Sináptico:** `{weight}`")

                related = self.memory_manager.get_working_context(str(path), limit=5)
                if related:
                    content.append("- **Nós Relacionados (Sinapses):**")
                    for r in related:
                        r_path = Path(r)
                        r_mirror = Path(self._get_mirror_file_path(r_path)).stem
                        content.append(f"  - [[{r_mirror}|{r_path.name}]]")

        with open(mirror_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

    def _create_file_note(self, path: Path):
        """Generates a note for a file."""
        mirror_path = self._get_mirror_file_path(path)
        os.makedirs(os.path.dirname(mirror_path), exist_ok=True)

        size_bytes = 0
        try:
            size_bytes = path.stat().st_size
        except Exception:
            pass

        content = [
            f"# Arquivo: {path.name}",
            "",
            f"**Caminho Original:** `{path}`",
            f"**Tipo:** `{path.suffix or 'unknown'}`",
            f"**Tamanho:** `{size_bytes / 1024:.2f} KB`",
            f"**Data de Mapeamento:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Parent link
        if path.parent:
            parent_mirror = Path(self._get_mirror_file_path(path.parent)).stem
            content.append(
                f"**Localização:** [[{parent_mirror}|📁 {path.parent.name}]]"
            )

        # Synaptic Context
        if self.memory_manager:
            weight = self._get_synaptic_weight(str(path))
            if weight > 1:
                content.append("")
                content.append("## Inteligência NEXUS")
                content.append(f"- **Peso Sináptico:** `{weight}`")

                related = self.memory_manager.get_working_context(str(path), limit=5)
                if related:
                    content.append("- **Conexões Sinápticas:**")
                    for r in related:
                        r_path = Path(r)
                        r_mirror = Path(self._get_mirror_file_path(r_path)).stem
                        content.append(f"  - [[{r_mirror}|{r_path.name}]]")

        with open(mirror_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

    def _get_synaptic_weight(self, path: str) -> int:
        """Gets weight from MemoryManager."""
        if not self.memory_manager:
            return 0
        import sqlite3

        try:
            conn = sqlite3.connect(self.memory_manager.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT weight FROM nodes WHERE path = ?", (path,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
            return 0
