# ZEUS COGNITIVE OS CORE — VERSION 3.0 (PRODUCTION-GRADE)
# PHASE 0: BOOTSTRAP MODE & PHASE 1: ORCHESTRATOR

import asyncio
import time
import os
import logging
from enum import Enum
from nexus_core.peripherals.usb_monitor import usb_monitor
from nexus_core.peripherals.bluetooth_monitor import bluetooth_monitor

# --- CONFIGURAÇÕES DE SEGURANÇA GLOBAL ---
ALLOWED_ORIGINS = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]

# --- PHASE 0: BOOTSTRAP MODE (MANDATORY) ---


class ExecutionMode(Enum):
    SAFE = "SAFE"  # Simulation only, no real execution
    DEV = "DEV"  # Limited execution, restricted commands
    AUTONOMOUS = "AUTONOMOUS"  # Full system operation


class BootstrapConfig:
    """Configuration for Bootstrap Phase 0. Enforces safety."""

    def __init__(self):
        # Load mode from environment, fallback to SAFE
        env_mode = os.getenv("NEXUS_MODE", "SAFE").upper()
        try:
            self.mode = ExecutionMode[env_mode]
        except KeyError:
            self.mode = ExecutionMode.SAFE

        # Log centralizado na pasta logs/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_file = os.path.join(project_root, "logs", "zeus_boot.log")
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger("NEXUS_BOOTSTRAP")

    def set_mode(self, mode_str: str):
        """Safely switch modes."""
        try:
            new_mode = ExecutionMode[mode_str.upper()]
            old_mode = self.mode
            self.mode = new_mode
            self.logger.info(f"Mode switched: {old_mode.value} -> {new_mode.value}")
            print(f"ZEUS MODE: {old_mode.value} -> {new_mode.value}")
        except KeyError:
            self.logger.error(f"Invalid mode attempt: {mode_str}")
            print(f"ERROR: Invalid mode '{mode_str}'. Use SAFE, DEV, or AUTONOMOUS.")

    def is_execution_allowed(self, command: str) -> bool:
        """Guardian Rule 1: Check if command can run in current mode."""
        dangerous_tokens = ["rm -rf", "sudo", "mkfs", "chmod 777", "dd if=", "shutdown"]

        if self.mode == ExecutionMode.SAFE:
            return False  # Nothing runs

        if self.mode == ExecutionMode.DEV:
            for token in dangerous_tokens:
                if token in command:
                    self.logger.warning(
                        f"DEV MODE: Blocked dangerous command: {command}"
                    )
                    return False
            return True

        if self.mode == ExecutionMode.AUTONOMOUS:
            # In Autonomous, Guardian (Phase 5) will handle deep validation
            # Here we only allow it to pass to the next layer
            return True

        return False


# --- PHASE 1: COGNITIVE ORCHESTRATOR ---


class CognitiveOrchestrator:
    """
    PHASE 1: The central brain loop.
    Manages perception -> thoughts -> goal -> plan -> simulation -> validation -> execution -> learning
    """

    def __init__(self, bootstrap_config: BootstrapConfig):
        self.config = bootstrap_config
        self.is_running = False
        self.loop_delay = 1.0  # Base delay
        self.cycle_count = 0

    async def start(self):
        """Starts the infinite cognitive loop."""
        self.is_running = True
        self.config.logger.info("Cognitive Orchestrator STARTED.")
        print("ZEUS CORE: Orchestrator initialized. Awaiting Blackboard...")

        while self.is_running:
            start_time = time.time()

            try:
                await self.cognitive_cycle()
            except Exception as e:
                self.config.logger.critical(
                    f"Orchestrator Cycle Error: {e}", exc_info=True
                )
                # In production, this would trigger Phase 11 (Self-Recovery)

            # Adaptive Delay (Phase 9 Resource Control - Lite)
            elapsed = time.time() - start_time
            if elapsed < self.loop_delay:
                await asyncio.sleep(self.loop_delay - elapsed)

            self.cycle_count += 1

            # Log heartbeat every 10 cycles
            if self.cycle_count % 10 == 0:
                self.config.logger.info(
                    f"Heartbeat: Cycle {self.cycle_count} | Mode: {self.config.mode.value}"
                )

    async def cognitive_cycle(self):
        """
        Executes one full cognitive cycle.
        """
        # 1. Perception
        await self._perceive()

        # 2. Reasoning / Goal Check
        await self._reason()

        # 3. Execution Check (Safety Validation)
        if self.config.mode == ExecutionMode.SAFE:
            pass

    async def _perceive(self):
        """Analyze recent system state."""
        if self.config.mode == ExecutionMode.AUTONOMOUS:
            # Placeholder for actual analysis logic
            if self.cycle_count % 600 == 0:  # Every ~10 minutes
                self.config.logger.info(
                    "AUTONOMOUS: Analyzing recent synaptic patterns..."
                )
                # Here we would call the LLM to 'reflect' on the state

    async def _reason(self):
        """Decide on proactive actions."""
        if self.config.mode == ExecutionMode.AUTONOMOUS:
            if self.cycle_count % 600 == 0:
                self.config.logger.info(
                    "AUTONOMOUS: Generating proactive cognitive insight."
                )
                # This would eventually broadcast to the UI

    def stop(self):
        """Safely stop the orchestrator."""
        self.is_running = False
        self.config.logger.info("Cognitive Orchestrator STOPPED.")
        print("ZEUS CORE: Orchestrator stopped.")


# --- MAIN ENTRY POINT FOR CORE v3.0 ---


async def run_nexus_core():
    """Entry point for the new Production Core."""
    config = BootstrapConfig()
    print(f"ZEUS v3.0 Booting in {config.mode.value} MODE.")
    orchestrator = CognitiveOrchestrator(config)

    # Iniciar Monitores de Periféricos
    usb_monitor.start()
    bluetooth_monitor.start()

    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(run_nexus_core())
