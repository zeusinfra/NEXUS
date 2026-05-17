import os
from typing import List, Dict
from nexus_core.conversation.turn_store import turn_store
from nexus_core.events.event_bus import event_bus, EventType


class ContextBuilder:
    """Constrói o contexto para a LLM baseado em prioridade e orçamentos de tokens."""

    def __init__(self):
        self.max_chars = int(os.getenv("NEXUS_CONTEXT_BUDGET_CHARS", "32000"))

        # Budgets relativos
        self.budgets = {
            "system_prompt": 0.20,
            "current_message": 0.15,
            "active_goal": 0.05,
            "recent_errors": 0.05,
            "active_files": 0.10,
            "arch_decisions": 0.10,
            "summary": 0.05,
            "vector_memory": 0.15,
            "history": 0.15,
        }

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[-max_len:] + "\n[...Truncado devido ao limite de contexto...]"

    async def build_context(
        self,
        session_id: str,
        current_message: str,
        system_prompt: str,
        active_goal: str = "",
        recent_errors: List[str] = None,
        topic_id: str = "general",
    ) -> List[Dict[str, str]]:

        recent_errors = recent_errors or []
        messages = []

        # 1. System Prompt (Highest Priority)
        sys_budget = int(self.max_chars * self.budgets["system_prompt"])
        sys_content = self._truncate(system_prompt, sys_budget)
        messages.append({"role": "system", "content": sys_content})

        # Build context block
        context_parts = []

        # 3. Active Goal
        if active_goal:
            goal_budget = int(self.max_chars * self.budgets["active_goal"])
            context_parts.append(
                f"--- OBJETIVO ATUAL ---\n{self._truncate(active_goal, goal_budget)}"
            )

        # 4. Recent Errors
        if recent_errors:
            err_budget = int(self.max_chars * self.budgets["recent_errors"])
            err_text = "\n".join(recent_errors)
            context_parts.append(
                f"--- ERROS RECENTES ---\n{self._truncate(err_text, err_budget)}"
            )

        # 7-10. History / Summary for the specific topic
        hist_budget = int(self.max_chars * self.budgets["history"])
        turns = turn_store.get_turns_for_topic(session_id, topic_id)

        if turns:
            hist_text = "\n".join(
                [f"{t.role.upper()}: {t.content}" for t in turns[-5:]]
            )  # Ultimos 5 turnos
            if len(hist_text) > hist_budget:
                hist_text = self._truncate(hist_text, hist_budget)
                await event_bus.publish_async(
                    EventType.CONTEXT_TOO_LARGE, {"topic": topic_id}
                )
            context_parts.append(f"--- HISTÓRICO RECENTE DO TÓPICO ---\n{hist_text}")

        # Add context block if not empty
        if context_parts:
            messages.append({"role": "system", "content": "\n\n".join(context_parts)})

        # 2. Current Message
        msg_budget = int(self.max_chars * self.budgets["current_message"])
        msg_content = self._truncate(current_message, msg_budget)
        messages.append({"role": "user", "content": msg_content})

        return messages


context_builder = ContextBuilder()
