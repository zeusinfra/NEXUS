from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelResponse:
    provider: str
    model: str
    content: str
    ok: bool = True
    error: str = ""


class BaseModelClient(Protocol):
    provider: str

    def available(self) -> bool: ...

    def generate(self, prompt: str, *, model: str | None = None) -> ModelResponse: ...
