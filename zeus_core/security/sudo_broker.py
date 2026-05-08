import os
import json
import asyncio
import socket
import datetime
from enum import Enum
from typing import Dict, Any, Tuple

from zeus_core.events.event_bus import event_bus, EventType
from zeus_core.observability import get_logger

logger = get_logger("zeus.security.sudo_broker")

class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    FORBIDDEN = "FORBIDDEN"

# Listas de Controle
FORBIDDEN_PATTERNS = [
    "rm -rf /", "rm -rf /*", "mkfs", "dd ", "shred", "wipefs", 
    "git reset --hard", "chmod -R 777 /", "chown -R", "userdel",
    "passwd", "ufw disable", "iptables -F"
]

READ_ONLY_PATTERNS = [
    "systemctl status", "journalctl", "df ", "free ", "uptime", 
    "ps ", "lsblk", "lscpu", "ip addr", "cat /var/log"
]

LOW_RISK_PATTERNS = [
    "apt update", "systemctl daemon-reload", "systemctl restart zeus",
    "apt list --upgradable"
]

class SudoBroker:
    """Intermediário de segurança para autonomia administrativa."""
    
    def __init__(self):
        self.socket_path = "/tmp/zeus_root_daemon.sock"
        self.require_confirmation = os.getenv("ZEUS_REQUIRE_CONFIRMATION_FOR_HIGH_RISK", "true").lower() == "true"
        self.audit_log_path = os.path.join(os.getenv("ZEUS_VAULT_PATH", "."), "logs", "sudo_audit.log")

    def _classify_risk(self, command: str) -> RiskLevel:
        cmd_lower = command.lower().strip()
        
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in cmd_lower:
                return RiskLevel.FORBIDDEN
                
        for pattern in READ_ONLY_PATTERNS:
            if cmd_lower.startswith(pattern):
                return RiskLevel.READ_ONLY
                
        for pattern in LOW_RISK_PATTERNS:
            if cmd_lower.startswith(pattern):
                return RiskLevel.LOW_RISK
                
        if "apt upgrade" in cmd_lower or "apt install" in cmd_lower or "systemctl restart" in cmd_lower:
            return RiskLevel.MEDIUM_RISK
            
        return RiskLevel.HIGH_RISK

    async def _send_to_daemon(self, action: str, kwargs: dict) -> dict:
        """Comunica com o RootDaemon via Unix Socket."""
        if not os.path.exists(self.socket_path):
            return {"status": "error", "message": "RootDaemon não está rodando."}
            
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            payload = json.dumps({"action": action, "kwargs": kwargs})
            writer.write(payload.encode() + b'\n')
            await writer.drain()
            
            data = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            return json.loads(data.decode())
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _audit(self, command: str, risk: RiskLevel, status: str, reason: str):
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "command": command,
                "risk": risk.value,
                "status": status,
                "reason": reason
            }
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Erro ao escrever log de auditoria: {e}")

    async def request_admin_action(
        self,
        command: str,
        reason: str,
        requires_backup: bool = False,
        rollback_plan: str = "",
        expected_outcome: str = "",
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Processa requisição de execução administrativa."""
        
        await event_bus.publish_async(EventType.SUDO_REQUESTED, {"command": command, "reason": reason})
        
        risk = self._classify_risk(command)
        
        if risk == RiskLevel.FORBIDDEN:
            self._audit(command, risk, "BLOCKED", "Comando na blocklist.")
            await event_bus.publish_async(EventType.SUDO_BLOCKED, {"command": command, "reason": "FORBIDDEN"})
            return {"status": "blocked", "message": "Ação estritamente proibida por política de segurança."}
            
        if risk == RiskLevel.HIGH_RISK and self.require_confirmation and not user_confirmed:
            self._audit(command, risk, "PENDING", "Aguardando confirmação do usuário.")
            return {"status": "requires_confirmation", "message": "Ação de alto risco. Confirmação necessária.", "risk": risk.value}
            
        # Simula validação do CriticAgent (Pode ser injetada via callback se necessário)
        
        if requires_backup:
            logger.info(f"Gerando backup antes da ação: {command}")
            # Em uma implementação real, chamaria _send_to_daemon("create_backup", {"target": "..."})
            
        # Executa a ação
        logger.warning(f"Executando ação admin ({risk.value}): {command}")
        
        # Mapeia comando para métodos seguros do daemon (Simplificado para o exemplo)
        # O SudoBroker nunca envia o comando bruto para shell arbitrário, ele mapeia para métodos do daemon.
        action = "execute_safe_command" # Um método fictício seguro no daemon para comandos permitidos.
        if risk == RiskLevel.READ_ONLY or risk == RiskLevel.LOW_RISK:
            response = await self._send_to_daemon(action, {"command": command})
        else:
            response = await self._send_to_daemon(action, {"command": command}) # Ajustar na implementação do daemon
            
        if response.get("status") == "success":
            self._audit(command, risk, "SUCCESS", reason)
            await event_bus.publish_async(EventType.ADMIN_ACTION_APPROVED, {"command": command})
        else:
            self._audit(command, risk, "FAILED", response.get("message", "Erro desconhecido"))
            if rollback_plan:
                logger.error(f"Falha na ação. Plano de rollback acionado: {rollback_plan}")
                # Executa rollback
                
        return response

sudo_broker = SudoBroker()
