import uuid
from typing import Dict, List, Any
from zeus_core.conversation.turn_store import turn_store, Turn
from zeus_core.conversation.topic_tracker import topic_tracker
from zeus_core.conversation.context_builder import context_builder
from zeus_core.conversation.response_sanitizer import response_sanitizer

class ConversationManager:
    """Gerencia o ciclo de vida completo de uma interação."""
    
    def __init__(self):
        self.active_sessions: Dict[str, str] = {} # session_id -> current_topic_id

    async def process_user_input(self, session_id: str, user_message: str, system_prompt: str) -> List[Dict[str, str]]:
        """Processa a entrada do usuário e constrói o prompt para a LLM."""
        
        # 1. Detectar Tópico
        topic_id = await topic_tracker.detect_topic_shift(user_message)
        self.active_sessions[session_id] = topic_id
        
        # 2. Salvar Turno do Usuário
        user_turn = Turn.create(
            session_id=session_id,
            role="user",
            content=user_message,
            topic_id=topic_id
        )
        turn_store.add_turn(user_turn)
        
        # 3. Construir Contexto
        # Na prática, active_goal e errors viriam do Blackboard/EventBus
        messages = await context_builder.build_context(
            session_id=session_id,
            current_message=user_message,
            system_prompt=system_prompt,
            topic_id=topic_id
        )
        
        return messages

    async def process_llm_response(self, session_id: str, response: str) -> str:
        """Sanitiza e salva a resposta da LLM."""
        
        # 1. Higienizar
        clean_response = await response_sanitizer.sanitize(response)
        
        # 2. Salvar Turno da LLM
        topic_id = self.active_sessions.get(session_id, "general")
        llm_turn = Turn.create(
            session_id=session_id,
            role="assistant",
            content=clean_response,
            topic_id=topic_id
        )
        turn_store.add_turn(llm_turn)
        
        return clean_response

conversation_manager = ConversationManager()
