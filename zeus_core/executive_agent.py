import os
import asyncio
from collections import Counter
from typing import Dict, List, Optional

class ExecutiveAgent:
    """Agente Executivo para Proatividade no ZEUS.
    Monitora padrões para sugerir ou executar ações sem solicitação direta.
    """
    def __init__(self):
        self.action_queue = asyncio.Queue()
        self.recent_commands: Dict[str, int] = Counter()
        self.stuck_threshold = 3  # Quantas edições repetidas indicam "travamento"
        self.file_edits: Dict[str, int] = Counter()

    async def monitor_event_stream(self, event):
        """Analisa cada evento em busca de gatilhos para intervenção."""
        if event.get("type") == "FILE_EVENT":
            await self._analyze_file_focus(event)
            await self._detect_loop_pattern(event)

    async def _analyze_file_focus(self, event):
        """Detecta mudança de contexto para sugerir abertura de arquivos relacionados."""
        pass  # Será integrado ao WebSocket via broadcast

    async def _detect_loop_pattern(self, event):
        """Detecta se o usuário está editando o mesmo arquivo repetidamente (possível erro/travamento)."""
        path = event.get("path")
        if not path:
            return
        
        self.file_edits[path] += 1
        
        # Se o usuário editou o mesmo arquivo 4 vezes em rápida sucessão...
        if self.file_edits[path] >= self.stuck_threshold:
            await self.action_queue.put({
                "type": "SUGGEST_BREAK",
                "target": path,
                "message": "Detectei alta iteração neste arquivo. Deseja que eu analise em busca de erros de sintaxe?",
                "action_context": "stuck_loop"
            })
            # Reseta o contador para evitar spam
            self.file_edits[path] = 0

    async def process_actions(self, broadcast_func):
        """Processa a fila de ações e envia para o frontend ou executa."""
        while True:
            action = await self.action_queue.get()
            
            if action["type"] == "SUGGEST_BREAK":
                # Envia a sugestão para o frontend
                await broadcast_func({
                    "type": "EXECUTIVE_INTERVENTION",
                    "priority": "high",
                    "log": {
                        "channel": "executive",
                        "title": "Padrão Detectado",
                        "detail": action["message"],
                        "meta": f"loops={self.stuck_threshold}"
                    }
                })
            elif action["type"] == "AUTO_OPEN":
                # Ação automática: abre arquivo ou URL
                # (Implementação segura requer permissão posterior)
                pass
            
            self.action_queue.task_done()

    def reset_context(self):
        """Limpa o contexto de curto prazo."""
        self.file_edits.clear()
