import os
import re
import hashlib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

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
