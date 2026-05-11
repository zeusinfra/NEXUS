import os
import re
import hashlib
from datetime import datetime

from zeus_core.env import load_project_env

load_project_env()

VAULT_PATH = os.getenv("ZEUS_VAULT_PATH", "/home/zeus/Documentos/Brain")

def calculate_content_hash(content: str) -> str:
    """Calcula SHA-256 do conteúdo para detectar alterações."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def extract_tags(content: str) -> list[str]:
    """Extrai tags do markdown, e.g. #to-notion, ignorando headers # Header."""
    # Procura por # seguido de letras/números/hífens, mas não quando seguido de espaço (que seria um header H1)
    tags = set(re.findall(r'(?<!\w)#([a-zA-Z0-9\-_]+)', content))
    return [f"#{tag}" for tag in tags]

def extract_internal_links(content: str) -> list[str]:
    """Extrai wikilinks estilo Obsidian: [[Link]]"""
    links = set(re.findall(r'\[\[(.*?)\]\]', content))
    return list(links)

def read_note(path: str) -> dict:
    """Lê uma nota Markdown e extrai seus metadados."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Nota não encontrada: {path}")
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    title = os.path.basename(path).replace(".md", "")
    tags = extract_tags(content)
    links = extract_internal_links(content)
    content_hash = calculate_content_hash(content)
    
    return {
        "title": title,
        "content": content,
        "tags": tags,
        "internal_links": links,
        "hash": content_hash,
        "path": path
    }

def write_obsidian_insight(title: str, content: str, folder: str = "Insights") -> str:
    """Escreve uma reflexão ou insight gerado pelo ZEUS diretamente no Obsidian."""
    folder_path = os.path.join(VAULT_PATH, folder)
    os.makedirs(folder_path, exist_ok=True)
    
    # Sanitiza título para nome de arquivo
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    file_path = os.path.join(folder_path, f"{safe_title}.md")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"---\ntags: [zeus-insight, auto-generated]\ndate: {timestamp}\n---\n\n"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(header + content)
        
    return file_path


def write_sync_note(subfolder: str, filename: str, content: str) -> str:
    """
    Escreve uma nota de sincronização na estrutura ZEUS_Sync/ do vault.
    Cria subpastas automaticamente. Sobrescreve o arquivo se existir.
    """
    sync_folder = os.path.join(VAULT_PATH, "ZEUS_Sync", subfolder)
    os.makedirs(sync_folder, exist_ok=True)
    
    safe_name = re.sub(r'[\\/*?:"<>|]', "", filename)
    if not safe_name.endswith('.md'):
        safe_name += '.md'
    
    file_path = os.path.join(sync_folder, safe_name)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"---\ntags: [zeus-sync, auto-generated]\ndate: {timestamp}\n---\n\n"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(header + content)
    
    return file_path


def update_daily_log(entries: list[str], date_str: str = None) -> str:
    """
    Append de entradas ao log diário em ZEUS_Sync/Daily/.
    Cria o arquivo se não existir, adicionando novas entradas sem apagar as antigas.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    daily_folder = os.path.join(VAULT_PATH, "ZEUS_Sync", "Daily")
    os.makedirs(daily_folder, exist_ok=True)
    
    file_path = os.path.join(daily_folder, f"{date_str}.md")
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing = f.read()
    else:
        existing = f"---\ntags: [zeus-daily, auto-generated]\ndate: {date_str}\n---\n\n# ZEUS Daily Log — {date_str}\n\n"
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    new_block = f"\n## {timestamp}\n\n"
    for entry in entries:
        new_block += f"- {entry}\n"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(existing + new_block)
    
    return file_path
