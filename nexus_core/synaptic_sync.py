import asyncio
import json
import logging
import httpx
from datetime import datetime
from nexus_core.memory_manager import MemoryManager

logger = logging.getLogger("NEXUS_SYNC")

class SyncEngine:
    """
    NEXUS Sync Engine: Sincroniza o grafo sináptico entre múltiplas instâncias do NEXUS.
    Permite que o aprendizado em um PC seja transferido para outro (Cérebro Ubíquo).
    """

    def __init__(self, memory_manager: MemoryManager, relay_url: str = None):
        self.memory_manager = memory_manager
        self.relay_url = relay_url or "https://relay.nexus-protocol.io"
        self.is_running = False
        self.last_sync = None

    async def export_neural_snapshot(self):
        """Gera um snapshot compactado do estado atual do cérebro."""
        return self.memory_manager.export_sync_snapshot()

    async def import_neural_snapshot(self, snapshot: dict):
        """Mescla um snapshot externo com a memória local."""
        logger.info("🧬 [SYNC] Mesclando conhecimento externo no DNA local...")
        
        # Mesclar nós
        for node in snapshot.get("top_nodes", []):
            self.memory_manager.update_synapse(node["path"], node["path"], weight_inc=0)
            
        # Mesclar sinapses
        for synapse in snapshot.get("top_synapses", []):
            self.memory_manager.update_synapse(
                synapse["source"], 
                synapse["target"], 
                weight_inc=synapse["weight"] // 2 # Transfere metade da 'força' para evitar choque
            )
            
        self.last_sync = datetime.now().isoformat()
        logger.info(f"✅ [SYNC] Sincronização concluída: {len(snapshot.get('top_synapses', []))} conexões assimiladas.")

    async def sync_loop(self):
        """Loop de sincronização periódica (se configurado)."""
        if not self.relay_url:
            return
            
        self.is_running = True
        logger.info(f"📡 [SYNC] Nexus Relay ativo: {self.relay_url}")
        
        while self.is_running:
            try:
                # Intervalo de 15 minutos para sincronização de fundo
                await asyncio.sleep(900)
                
                snapshot = await self.export_neural_snapshot()
                # Aqui seria a chamada real para o relay
                # await self._post_to_relay(snapshot)
                
                logger.info("📡 [SYNC] Snapshot neural enviado para o Relay.")
            except Exception as e:
                logger.error(f"❌ [SYNC] Erro no loop de sincronização: {e}")
                await asyncio.sleep(60)

    async def _post_to_relay(self, snapshot):
        async with httpx.AsyncClient() as client:
            await client.post(f"{self.relay_url}/sync", json=snapshot)
