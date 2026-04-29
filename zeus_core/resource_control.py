
import psutil
import logging
import asyncio
from typing import Dict, Any

class ResourceControl:
    """
    PHASE 9: Resource Control.
    System stability enforcement.
    Monitors hardware and throttles the cognitive loop to prevent system crashes.
    """
    def __init__(self, blackboard, bootstrap_config):
        self.blackboard = blackboard
        self.config = bootstrap_config
        self.logger = logging.getLogger("ZEUS_RESOURCES")
        
        # Thresholds
        self.CPU_CRITICAL = 92.0  # Percent (Aumentado para evitar pausas excessivas)
        self.RAM_CRITICAL = 95.0  # Percent (Aumentado para evitar pausas excessivas)
        self.min_delay = 0.1       # Max speed (10Hz)
        self.max_delay = 5.0       # Min speed (Emergency throttle)

    def get_system_snapshot(self) -> Dict[str, float]:
        """Captures current hardware utilization."""
        return {
            "cpu": psutil.cpu_percent(interval=None),
            "ram": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent
        }

    def calculate_adaptive_delay(self, current_delay: float) -> float:
        """
        Calculates the next loop delay based on system pressure.
        If CPU/RAM is high, it increases delay (throttling).
        If system is idle, it decreases delay (acceleration).
        """
        snapshot = self.get_system_snapshot()
        cpu = snapshot["cpu"]
        ram = snapshot["ram"]
        
        # Pressure logic
        if self.is_critical(snapshot):
            # Critical pressure: Increase delay significantly
            new_delay = min(self.max_delay, current_delay * 1.5)
            self.logger.warning(f"CRITICAL PRESSURE: Throttling loop. CPU: {cpu}%, RAM: {ram}%")
        elif cpu < 20.0 and ram < 60.0:
            # Low pressure: Slightly accelerate
            new_delay = max(self.min_delay, current_delay * 0.9)
        else:
            # Stable: Keep current delay
            new_delay = current_delay
            
        return new_delay

    def is_critical(self, snapshot: Dict[str, float] = None) -> bool:
        """Checks if the system is under critical pressure."""
        if snapshot is None:
            snapshot = self.get_system_snapshot()
        return snapshot["cpu"] > self.CPU_CRITICAL or snapshot["ram"] > self.RAM_CRITICAL

    async def monitor_and_report(self):
        """Continuously updates Blackboard with resource usage."""
        while True:
            snapshot = self.get_system_snapshot()
            self.blackboard.update("system_resources", {
                "cpu": snapshot["cpu"],
                "ram": snapshot["ram"],
                "disk": snapshot["disk"],
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Trigger alert if critical
            if snapshot["cpu"] > self.CPU_CRITICAL or snapshot["ram"] > self.RAM_CRITICAL:
                self.logger.error(f"Resource Exhaustion Warning: CPU {snapshot['cpu']}% RAM {snapshot['ram']}%")
                
            await asyncio.sleep(2.0) # Monitor every 2 seconds
