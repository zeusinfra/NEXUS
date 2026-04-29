# Exemplo de como usar o módulo Rust dentro do Python (ZEUS System)
# Para rodar isso, você compilaria o Rust com 'maturin develop' ou 'cargo build --release'

try:
    # O módulo compilado apareceria como uma biblioteca normal
    import zeus_memory
    print("🚀 Módulo Rust carregado com sucesso!")
except ImportError:
    print("❌ Módulo Rust não encontrado. (Apenas demonstração conceitual)")
    # Fallback para o código que explica o uso
    class MockRust:
        def VectorMemoryRust(self): return self
        def add_vector(self, k, v): pass
        def find_similar(self, q, k): return [("file.txt", 0.98)]
    zeus_memory = MockRust()

# No seu core_system.py ou web_gui.py:
rust_memory = zeus_memory.VectorMemoryRust()

# Simulando adição de um vetor (geralmente vindo do Ollama/Gemini)
# Em Rust, isso é instantâneo e gasta muito menos RAM
vector = [0.1, 0.5, -0.2, 0.8] # Exemplo de embedding
rust_memory.add_vector("configs/projeto_x.py", vector)

# A mágica acontece aqui: 
# Mesmo com 100.000 vetores, o Rust calculará a similaridade em milissegundos
query_vector = [0.12, 0.48, -0.18, 0.81]
results = rust_memory.find_similar(query_vector, top_k=5)

for path, score in results:
    print(f"📄 Arquivo: {path} | Similaridade: {score:.4f}")
