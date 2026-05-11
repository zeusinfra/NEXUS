import time
import asyncio
from zeus_core.events.event_bus import event_bus, EventType


class ExecutiveAgent:
    """Agente Executivo para Proatividade no ZEUS.
    Monitora padrões para sugerir ou executar ações sem solicitação direta.
    """

    def __init__(self):
        self.action_queue = asyncio.Queue()
        self.stuck_score = 0
        self.recent_files_touched: set = set()
        self.last_files_reset = time.time()
        self.conversation_concat_detected = False

        # Inscreve nos eventos do bus
        event_bus.subscribe(EventType.FILE_CHANGED, self._on_file_changed)
        event_bus.subscribe(EventType.COMMAND_FAILED, self._on_failure)
        event_bus.subscribe(EventType.BUILD_FAILED, self._on_failure)
        event_bus.subscribe(EventType.TOOL_FAILED, self._on_failure)
        event_bus.subscribe(EventType.CONVERSATION_CONCAT_DETECTED, self._on_concat)

    async def _on_failure(self, event):
        self.stuck_score += 1
        await self._evaluate_stuck_state()

    async def _on_concat(self, event):
        self.conversation_concat_detected = True
        self.stuck_score += 1
        await self.action_queue.put(
            {
                "type": "SUGGEST_CONTEXT_REBUILD",
                "message": "Detectei concatenação excessiva na conversa. Deseja que eu limpe o contexto para focar no objetivo atual?",
            }
        )
        await self._evaluate_stuck_state()

    async def _on_file_changed(self, event):
        path = event.payload.get("path") or event.payload.get("source_path")
        if not path:
            return

        now = time.time()
        if now - self.last_files_reset > 60:  # 1 minute
            self.recent_files_touched.clear()
            self.last_files_reset = now

        self.recent_files_touched.add(path)

        if len(self.recent_files_touched) >= 4:
            await self.action_queue.put(
                {
                    "type": "SUGGEST_ARCHITECTURE_REVIEW",
                    "message": "Você modificou muitos arquivos rapidamente. Deseja uma revisão arquitetural para garantir a consistência?",
                }
            )
            self.recent_files_touched.clear()

        self.stuck_score += 0.2
        await self._evaluate_stuck_state()

    async def _evaluate_stuck_state(self):
        if self.stuck_score >= 5:
            await self.action_queue.put(
                {
                    "type": "SUGGEST_BREAK",
                    "message": "Detectei vários erros ou repetições. Deseja que eu faça uma análise profunda do problema atual?",
                }
            )
            self.stuck_score = 0

    async def process_actions(self, broadcast_func):
        """Processa a fila de ações e envia para o frontend."""
        while True:
            action = await self.action_queue.get()

            await broadcast_func(
                {
                    "type": "EXECUTIVE_INTERVENTION",
                    "priority": "high",
                    "log": {
                        "channel": "executive",
                        "title": "Intervenção Proativa",
                        "detail": action["message"],
                        "meta": f"action={action['type']}",
                    },
                }
            )

            self.action_queue.task_done()

    def reset_context(self):
        """Limpa o contexto de curto prazo."""
        self.stuck_score = 0
        self.recent_files_touched.clear()
        self.conversation_concat_detected = False


executive_agent = ExecutiveAgent()
