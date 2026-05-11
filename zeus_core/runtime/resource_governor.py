import asyncio
import os
import psutil
from typing import Optional
from zeus_core.events.event_bus import event_bus, EventType


class ResourceGovernor:
    """Monitora CPU, RAM, swap e disco, disparando eventos e ajustando o sistema."""

    def __init__(self):
        self.cpu_limit = float(os.getenv("ZEUS_CPU_SOFT_LIMIT", "65"))
        self.ram_limit = float(os.getenv("ZEUS_RAM_SOFT_LIMIT", "75"))
        self.swap_limit = float(os.getenv("ZEUS_SWAP_SOFT_LIMIT", "50"))
        self.disk_min_free = float(os.getenv("ZEUS_DISK_MIN_FREE_PERCENT", "10"))
        self.zeus_mode = os.getenv("ZEUS_MODE", "BALANCED").upper()

        self.is_low_resource_mode = False
        self.high_cpu_consecutive_checks = 0
        self.check_interval_seconds = 10
        self._task: Optional[asyncio.Task] = None

    async def _monitor_loop(self):
        while True:
            try:
                await self._check_resources()
            except Exception as e:
                print(f"[ResourceGovernor] Erro ao checar recursos: {e}")
            await asyncio.sleep(self.check_interval_seconds)

    async def _check_resources(self):
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent

        # Swap safely
        swap_info = psutil.swap_memory()
        swap = swap_info.percent if swap_info.total > 0 else 0

        disk = psutil.disk_usage("/").percent
        disk_free = 100 - disk

        issues = []

        if cpu > self.cpu_limit:
            self.high_cpu_consecutive_checks += 1
            if self.high_cpu_consecutive_checks >= 6:  # ~1 min
                issues.append("CPU")
                await event_bus.publish_async(EventType.HIGH_CPU_USAGE, {"cpu": cpu})
        else:
            self.high_cpu_consecutive_checks = 0

        if ram > self.ram_limit:
            issues.append("RAM")
            await event_bus.publish_async(EventType.HIGH_RAM_USAGE, {"ram": ram})

        if swap > self.swap_limit:
            issues.append("SWAP")
            await event_bus.publish_async(EventType.HIGH_SWAP_USAGE, {"swap": swap})

        if disk_free < self.disk_min_free:
            issues.append("DISK")
            await event_bus.publish_async(EventType.DISK_PRESSURE, {"free": disk_free})

        was_low = self.is_low_resource_mode
        if self.zeus_mode == "AGGRESSIVE":
            self.is_low_resource_mode = False
        else:
            self.is_low_resource_mode = len(issues) > 0

        if self.is_low_resource_mode and not was_low:
            print(
                f"[ResourceGovernor] Ativando LOW_RESOURCE mode devido a: {', '.join(issues)}"
            )
        elif not self.is_low_resource_mode and was_low:
            print(
                "[ResourceGovernor] Recursos normalizados. Saindo do LOW_RESOURCE mode."
            )

    def get_cognitive_interval(self, current_interval: int) -> int:
        """Se estiver em LOW_RESOURCE, o intervalo base é sobrescrito ou aumentado."""
        if self.is_low_resource_mode:
            return int(os.getenv("ZEUS_COGNITIVE_INTERVAL_LOW_RESOURCE", "90"))
        return current_interval

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._monitor_loop())

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None


resource_governor = ResourceGovernor()
