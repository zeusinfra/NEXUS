from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Awaitable, Callable


class OverflowEventQueue:
    def __init__(self, maxsize: int):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize if maxsize and maxsize > 0 else 0)

    async def enqueue(self, event: dict) -> None:
        try:
            self.queue.put_nowait(event)
            return
        except asyncio.QueueFull:
            pass
        except Exception:
            return

        try:
            self.queue.get_nowait()
        except Exception:
            return
        try:
            self.queue.put_nowait(event)
        except Exception:
            return

    async def get(self) -> dict:
        return await self.queue.get()

    def get_nowait(self) -> dict:
        return self.queue.get_nowait()

    def empty(self) -> bool:
        return self.queue.empty()


class RustWatcherRunner:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.process = None
        self.started_at: float | None = None
        self.last_event_at: float | None = None

    def resolve_binary(self) -> str | None:
        candidates = [
            self.project_root / "watcher_rs" / "target" / "release" / "watcher_rs",
            self.project_root / "watcher_rs" / "target" / "debug" / "watcher_rs",
            self.project_root / "core-rust" / "target" / "release" / "zeus_core",
            self.project_root / "core-rust" / "target" / "debug" / "zeus_core",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    async def run(self, enqueue: Callable[[dict], Awaitable[None]]) -> None:
        binary_path = self.resolve_binary()
        if not binary_path:
            print("Rust watcher binary not found. Build watcher_rs before starting the GUI.")
            return

        process = await asyncio.create_subprocess_exec(
            binary_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.process = process
        self.started_at = time.time()
        stderr_task = asyncio.create_task(log_subprocess_stream(process.stderr, "watcher_rs"))
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line.decode())
                event = {
                    "type": "FILE_EVENT",
                    "event": data.get("event_type") or data.get("event_kind") or "Update",
                    "path": data["path"],
                    "project": data["project"],
                }
                self.last_event_at = time.time()
                await enqueue(event)
            except Exception as e:
                print(f"Error parsing Rust output: {e}")
        await stderr_task


async def log_subprocess_stream(stream, label: str) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break
        print(f"[{label}] {line.decode(errors='ignore').rstrip()}")
