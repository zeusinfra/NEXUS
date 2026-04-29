from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional


ToolHandler = Callable[[dict], Any] | Callable[[dict], Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: ToolHandler
    available: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_specs(self) -> list[dict]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
                "available": spec.available,
            }
            for spec in self._tools.values()
        ]

