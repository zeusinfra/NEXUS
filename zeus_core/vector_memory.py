import json
import os
import requests
import numpy as np
from typing import List, Dict, Tuple

try:
    from zeus_memory import VectorMemoryRust
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False

class VectorMemory:
    """
    Memória Vetorial Simplificada para ZEUS.
    Utiliza embeddings do Ollama e armazena em JSON para máxima portabilidade.
    """
    def __init__(self, storage_file: str = "data/vector_memory.bin", embedding_model: str = "all-minilm"):
        self.storage_file = storage_file
        self.model = embedding_model
        self.url = "http://127.0.0.1:11434/api/embeddings"
        self.max_vectors = int(os.getenv("ZEUS_VECTOR_MAX", "5000") or "5000")
        
        if RUST_AVAILABLE:
            print("🦀 ZEUS: Usando Backend Rust para Memória Vetorial.")
            self.rust_mem = VectorMemoryRust(storage_file)
            self.vectors = self.rust_mem.vectors
        else:
            print("🐍 ZEUS: Usando Backend Python para Memória Vetorial.")
            self.rust_mem = None
            self.vectors: Dict[str, List[float]] = {}
            self.load()

    def _evict_if_needed(self) -> None:
        """
        Mantém o uso de RAM sob controle removendo embeddings antigos.
        Dict mantém ordem de inserção em Python 3.7+.
        """
        limit = self.max_vectors
        if not limit or limit <= 0:
            return
        over = len(self.vectors) - limit
        if over <= 0:
            return
        try:
            for key in list(self.vectors.keys())[:over]:
                self.vectors.pop(key, None)
        except Exception:
            pass

    def _get_embedding(self, text: str) -> List[float]:
        """Solicita o vetor de embedding para um texto ao Ollama."""
        try:
            response = requests.post(
                self.url, 
                json={"model": self.model, "prompt": text}, 
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("embedding", [])
        except Exception as e:
            print(f"Embedding Error: {e}")
        return []

    def index_file(self, path: str):
        """Lê o conteúdo de um arquivo e armazena seu embedding."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if content.strip():
                    vector = self._get_embedding(content[:5000])
                    if vector:
                        if self.rust_mem:
                            self.rust_mem.add_vector(path, vector)
                        else:
                            self.vectors[path] = vector
                            self._evict_if_needed()
                        # self.save() # REMOVIDO: Evita disk thrashing. web_gui gerencia persistência.
        except Exception as e:
            print(f"Indexing Error ({path}): {e}")

    def index_text(self, key: str, text: str):
        """Armazena o embedding de um texto arbitrário (ex: contexto web)."""
        if not text or not text.strip():
            return
        vector = self._get_embedding(text[:5000])
        if vector:
            if self.rust_mem:
                self.rust_mem.add_vector(key, vector)
            else:
                self.vectors[key] = vector
                self._evict_if_needed()
            # self.save() # REMOVIDO: web_gui gerencia persistência.

    def find_similar(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Encontra os arquivos mais similares semanticamente à query."""
        query_vector = self._get_embedding(query)
        if not query_vector:
            return []

        if self.rust_mem:
            return self.rust_mem.find_similar(query_vector, top_k)

        similarities = []
        for path, vector in self.vectors.items():
            try:
                dot_product = np.dot(query_vector, vector)
                norm_q = np.linalg.norm(query_vector)
                norm_v = np.linalg.norm(vector)
                similarity = dot_product / (norm_q * norm_v) if norm_q * norm_v > 0 else 0
                similarities.append((path, similarity))
            except Exception:
                continue

        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]

    def find_similar_by_key(self, key: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Encontra vetores similares usando um vetor já armazenado como base."""
        query_vector = self.vectors.get(key)
        if not query_vector:
            return []

        similarities = []
        for path, vector in self.vectors.items():
            if path == key:
                continue
            try:
                dot_product = np.dot(query_vector, vector)
                norm_q = np.linalg.norm(query_vector)
                norm_v = np.linalg.norm(vector)
                similarity = dot_product / (norm_q * norm_v) if norm_q * norm_v > 0 else 0
                similarities.append((path, similarity))
            except Exception:
                continue

        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]

    def save(self):
        if self.rust_mem:
            try:
                self.rust_mem.save()
            except Exception as e:
                print(f"Rust Save Error: {e}")
            return

        try:
            # Atomic write: save to temp then rename to avoid corruption
            temp_file = self.storage_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.vectors, f, indent=2)
            os.replace(temp_file, self.storage_file)
        except Exception as e:
            print(f"Save Error: {e}")

    def load(self):
        if self.rust_mem:
            try:
                self.rust_mem.load()
            except Exception as e:
                print(f"Rust Load Error: {e}")
            return

        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.vectors = json.load(f)
            except Exception as e:
                print(f"Load Error: {e}")
