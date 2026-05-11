"""
ZEUS Cognitive Core — Cognition Service.

Standalone entry point for running the cognitive loop as a daemon.
Can be invoked via:
    python -m nexus_core.cognitive.cognition_service
    python -m nexus_core.cognitive

Also provides ``CognitionService`` for programmatic control from FastAPI.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

# Ensure project root is on sys.path when running standalone
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from nexus_core.cognitive.cognitive_db import init_cognitive_tables
from nexus_core.cognitive.cognitive_loop import CognitiveLoop
from nexus_core.cognitive.cognitive_state import cognitive_state_manager
from nexus_core.env import load_project_env
from nexus_core.observability import get_logger, log_event, setup_logging

load_project_env()

logger = get_logger("zeus.cognitive.service")


class CognitionService:
    """Manages the cognitive loop lifecycle.

    Use from FastAPI via ``start()`` / ``stop()`` or run standalone
    via ``run_forever()``.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self.loop = CognitiveLoop(db_path=db_path)
        self._task: asyncio.Task | None = None

    async def start(self) -> bool:
        """Start the cognitive loop as a background asyncio task."""
        if self._task and not self._task.done():
            log_event(logger, 30, "service_already_running")
            return False

        init_cognitive_tables(self.db_path)
        self._task = asyncio.create_task(self.loop.start())
        log_event(logger, 20, "cognition_service_started")
        return True

    async def stop(self) -> bool:
        """Stop the cognitive loop gracefully."""
        if not self._task or self._task.done():
            log_event(logger, 30, "service_not_running")
            return False

        await self.loop.stop()
        try:
            await asyncio.wait_for(self._task, timeout=10)
        except asyncio.TimeoutError:
            self._task.cancel()
            log_event(logger, 30, "service_force_cancelled")
        self._task = None
        log_event(logger, 20, "cognition_service_stopped")
        return True

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def get_status(self) -> dict:
        """Return the current cognitive state."""
        return cognitive_state_manager.get_snapshot()

    async def run_forever(self) -> None:
        """Run the cognitive loop until interrupted. For standalone daemon use."""
        setup_logging(os.getenv("NEXUS_LOG_LEVEL", "INFO"))
        log_event(
            logger,
            20,
            "cognition_daemon_starting",
            db_path=self.db_path or os.getenv("NEXUS_DB_PATH", "./zeus_events.db"),
        )

        loop = asyncio.get_running_loop()

        # Handle SIGTERM/SIGINT for clean daemon shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig, lambda: asyncio.create_task(self._shutdown(sig))
            )

        init_cognitive_tables(self.db_path)
        await self.loop.start()

    async def _shutdown(self, sig) -> None:
        log_event(logger, 20, "shutdown_signal_received", signal=str(sig))
        await self.loop.stop()


def main() -> None:
    """CLI entry point for the cognition daemon."""
    enabled = os.getenv("NEXUS_COGNITIVE_LOOP_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        print(
            "[NEXUS] Cognitive loop is disabled. "
            "Set NEXUS_COGNITIVE_LOOP_ENABLED=1 in .env to enable."
        )
        sys.exit(0)

    service = CognitionService()
    try:
        asyncio.run(service.run_forever())
    except KeyboardInterrupt:
        print("\n[NEXUS] Cognitive loop interrupted.")


if __name__ == "__main__":
    main()
