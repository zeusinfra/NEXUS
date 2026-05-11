import os
from zeus_core.conversation.context_builder import context_builder


class ContextManager:
    """
    Orquestrador final de contexto.
    Combina ContextBuilder (curto prazo/turno) com Memória Vetorial e Arquitetural.
    """

    def __init__(self):
        self.arch_decisions_path = os.path.join(
            os.getenv("ZEUS_VAULT_PATH", "."), "architecture_decisions.md"
        )

    def _get_architectural_decisions(self) -> str:
        if os.path.exists(self.arch_decisions_path):
            with open(self.arch_decisions_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    async def assemble_full_prompt(
        self,
        session_id: str,
        current_message: str,
        system_prompt: str,
        vector_memory_query: str = "",
    ) -> list:
        """
        Monta a lista de mensagens final misturando todos os recursos sem estourar budgets.
        """
        # 1. Recupera as decisões estáticas (DNA/Arch)
        arch_data = self._get_architectural_decisions()

        # 2. Em um sistema completo, aqui buscaria no ChromaDB / Vector Memory
        vector_data = ""  # Simulado
        if vector_memory_query:
            pass  # vector_data = get_from_chroma(vector_memory_query)

        # Modifica o system_prompt injetando a fundação arquitetural e memória
        enhanced_system_prompt = system_prompt
        if arch_data:
            enhanced_system_prompt += f"\n\n--- DECISÕES ARQUITETURAIS ---\n{arch_data}"
        if vector_data:
            enhanced_system_prompt += f"\n\n--- MEMÓRIA RELEVANTE ---\n{vector_data}"

        # 3. Chama o builder para a lógica fina de turnos e orçamentos
        messages = await context_builder.build_context(
            session_id=session_id,
            current_message=current_message,
            system_prompt=enhanced_system_prompt,
        )

        return messages


context_manager = ContextManager()
