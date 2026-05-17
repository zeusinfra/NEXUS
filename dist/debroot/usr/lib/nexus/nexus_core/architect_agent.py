import os
import json
import re
from nexus_core.core_system import call_cloud_llm

class ArchitectAgent:
    """
    O ARQUITETO do NEXUS: Especialista em design de sistemas e codificação autônoma.
    Capaz de planejar projetos inteiros e gerar código pronto para produção.
    """

    def __init__(self, project_root: str):
        self.project_root = project_root

    def plan_project(self, goal: str) -> dict:
        """Cria um blueprint completo para um novo projeto ou funcionalidade."""
        system_prompt = (
            "Você é o ARCHITECT do NEXUS. Seu objetivo é projetar sistemas robustos e modulares.\n"
            "Responda SEMPRE em formato JSON com a seguinte estrutura:\n"
            "{\n"
            "  \"project_name\": \"...\",\n"
            "  \"architecture\": \"...\",\n"
            "  \"files\": [{\"path\": \"...\", \"description\": \"...\", \"imports\": [...]}]\n"
            "}"
        )
        
        user_prompt = f"Objetivo do Projeto: {goal}\n\nPor favor, desenhe a estrutura de arquivos e a lógica central."
        
        response = call_cloud_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        try:
            # Busca o primeiro bloco JSON {...} usando Regex para evitar erros de markdown
            match = re.search(r'(\{.*\})', response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(response)
        except Exception as e:
            return {"error": f"Falha ao extrair JSON: {str(e)}", "raw": response}

    def generate_code(self, file_info: dict, context: str = "") -> str:
        """Gera o código fonte para um arquivo específico do blueprint."""
        system_prompt = (
            "Você é o CODING ENGINE do NEXUS. Escreva código limpo, documentado e funcional.\n"
            "Use padrões de design modernos e evite redundâncias."
        )
        
        user_prompt = (
            f"Arquivo: {file_info['path']}\n"
            f"Descrição: {file_info['description']}\n"
            f"Contexto do Projeto: {context}\n"
            "Escreva apenas o código completo do arquivo."
        )
        
        return call_cloud_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

    def analyze_file(self, path: str) -> dict:
        """Realiza uma auditoria profunda de um arquivo existente."""
        if not os.path.exists(path):
            return {"error": "Arquivo não encontrado."}
            
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        system_prompt = (
            "Você é o CODE ANALYST do NEXUS. Sua missão é identificar débitos técnicos e oportunidades de evolução.\n"
            "Analise o código fornecido e retorne um JSON:\n"
            "{\n"
            "  \"complexity\": \"low|medium|high\",\n"
            "  \"patterns_detected\": [...],\n"
            "  \"vulnerabilities\": [...],\n"
            "  \"synaptic_suggestions\": \"...\"\n"
            "}"
        )
        
        response = call_cloud_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analise este código:\n\n{content}"}
        ])
        
        try:
            match = re.search(r'(\{.*\})', response, re.DOTALL)
            return json.loads(match.group(1)) if match else json.loads(response)
        except:
            return {"raw_analysis": response}

    def suggest_refactor(self, path: str) -> str:
        """Propõe uma versão refatorada e otimizada de um arquivo."""
        analysis = self.analyze_file(path)
        
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        system_prompt = "Você é o REFACTORING ENGINE do NEXUS. Reescreva o código para ser mais elegante, rápido e seguro."
        user_prompt = f"Código Original:\n{content}\n\nDiagnóstico: {analysis.get('synaptic_suggestions')}\n\nReescreva o código completo:"
        
        return call_cloud_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

architect_agent = ArchitectAgent(os.getenv("NEXUS_PROJECT_ROOT", "."))
