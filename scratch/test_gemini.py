import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório raiz ao path para importar zeus_core
sys.path.append(os.getcwd())

load_dotenv()

try:
    from zeus_core.core_system import call_cloud_llm
    print("Iniciando teste de comunicação com Gemini...")
    response = call_cloud_llm([{"role": "user", "content": "Diga 'Sistemas ZEUS operacionais' em poucas palavras."}])
    print(f"Resposta do ZEUS: {response}")
except Exception as e:
    print(f"Erro durante o teste: {e}")
