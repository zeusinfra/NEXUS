import os
import asyncio
from zeus_core.events.event_bus import publish_file_event
from zeus_core.path_filters import IGNORED_RUNTIME_DIRS, is_runtime_noise_path

# In-memory cache of file modification times
_mtime_cache = {}

IGNORED_DIRS = IGNORED_RUNTIME_DIRS | {".trash"}


async def watch_vault(
    vault_path: str, poll_interval: float = 2.0, force_initial_scan: bool = False
):
    """
    Monitor leve de arquivos Markdown usando os.stat().
    Mantém o controle de mtime para detectar mudanças sem ler o conteúdo.
    """
    if not os.path.exists(vault_path):
        print(f"[Watcher] Vault path não encontrado: {vault_path}")
        return

    print(f"[Watcher] Monitorando: {vault_path}")

    # Fazemos um scan silencioso inicial para preencher o cache, a menos que forçado
    _initial_scan(vault_path, force=force_initial_scan)

    while True:
        await asyncio.sleep(poll_interval)
        try:
            _scan_for_changes(vault_path)
        except Exception as e:
            print(f"[Watcher] Erro durante o scan: {e}")


def _initial_scan(vault_path: str, force: bool = False):
    """Popula o cache inicial para evitar trigger em massa no boot."""
    count = 0
    for root, dirs, files in os.walk(vault_path):
        # Remove diretórios ignorados
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for file in files:
            path = os.path.join(root, file)
            if not file.endswith(".md") or is_runtime_noise_path(path):
                continue
            try:
                mtime = os.stat(path).st_mtime
                _mtime_cache[path] = mtime
                if force:
                    publish_file_event(path)
                count += 1
            except FileNotFoundError:
                pass
    print(f"[Watcher] Initial scan completo. {count} arquivos .md indexados.")


def _scan_for_changes(vault_path: str):
    """Verifica alterações comparando com o cache de mtime."""
    for root, dirs, files in os.walk(vault_path):
        # Filtra diretórios ignorados
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for file in files:
            path = os.path.join(root, file)
            if not file.endswith(".md") or is_runtime_noise_path(path):
                continue
            try:
                mtime = os.stat(path).st_mtime
                last_mtime = _mtime_cache.get(path)

                if last_mtime is None or mtime > last_mtime:
                    # Arquivo novo ou modificado
                    _mtime_cache[path] = mtime
                    publish_file_event(path)
            except FileNotFoundError:
                pass
