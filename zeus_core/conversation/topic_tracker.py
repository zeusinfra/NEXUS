import uuid
from typing import Dict, List
from zeus_core.events.event_bus import event_bus, EventType

class TopicTracker:
    """Rastreia mudanças de tópico na conversa para evitar mistura de contextos."""
    
    def __init__(self):
        self._current_topic_id = "general"
        self._topic_history: List[str] = ["general"]
        self._topic_keywords: Dict[str, List[str]] = {}

    def get_current_topic(self) -> str:
        return self._current_topic_id

    async def detect_topic_shift(self, user_message: str) -> str:
        """
        Analisa a mensagem para detectar se o usuário mudou de assunto.
        Retorna o topic_id (novo ou existente).
        """
        msg_lower = user_message.lower()
        
        # Heurística simples para detectar retorno a tópico anterior
        if any(ph in msg_lower for ph in ["voltando", "como falamos antes", "sobre aquele assunto"]):
            if len(self._topic_history) > 1:
                # Retorna ao tópico anterior (simplificado)
                self._current_topic_id = self._topic_history[-2]
                await event_bus.publish_async(EventType.CONVERSATION_TOPIC_SHIFT, {"new_topic": self._current_topic_id})
                return self._current_topic_id

        # Heurística para mudança drástica (Na prática, usaria LLM/Embeddings para similaridade)
        # Se a mensagem for muito longa ou introduzir conceitos chave totalmente novos, muda o tópico.
        # Por enquanto, assumimos mudança se o usuário explicitly pedir "mudando de assunto" ou iniciar nova task.
        if "mudando de assunto" in msg_lower or "agora quero" in msg_lower or "outra coisa" in msg_lower:
            new_topic = uuid.uuid4().hex[:8]
            self._current_topic_id = new_topic
            self._topic_history.append(new_topic)
            await event_bus.publish_async(EventType.CONVERSATION_TOPIC_SHIFT, {"new_topic": self._current_topic_id})
            return new_topic

        return self._current_topic_id

topic_tracker = TopicTracker()
