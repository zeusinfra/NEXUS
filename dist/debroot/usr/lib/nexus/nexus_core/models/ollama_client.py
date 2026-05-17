from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from nexus_core.models.base_model_client import ModelResponse


LOCAL_MODEL_PREFERENCE = (
    "qwen2.5:3b",
    "qwen2.5:1.5b",
    "gemma2:2b",
    "phi3:mini",
    "llama3.2:3b",
)


@dataclass(frozen=True)
class OllamaModel:
    name: str
    size: int | None = None
    modified_at: str | None = None


@dataclass(frozen=True)
class OllamaStatus:
    binary_found: bool
    binary_path: str | None
    api_ok: bool
    endpoint: str
    models: list[OllamaModel]
    selected_model: str | None
    error: str = ""

    @property
    def ready(self) -> bool:
        return self.binary_found and self.api_ok and bool(self.selected_model)


class OllamaClient:
    provider = "ollama"

    def __init__(
        self, endpoint: str = "http://localhost:11434", timeout_s: float = 3.0
    ):
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s

    def binary_path(self) -> str | None:
        return shutil.which("ollama")

    def available(self) -> bool:
        return self.status().ready

    def status(self) -> OllamaStatus:
        binary = self.binary_path()
        models: list[OllamaModel] = []
        api_ok = False
        error = ""
        try:
            models = self.list_models()
            api_ok = True
        except Exception as exc:
            error = str(exc)
            if binary:
                try:
                    models = self.list_models_cli()
                except Exception:
                    pass
        selected = choose_local_model([model.name for model in models])
        return OllamaStatus(
            binary_found=bool(binary),
            binary_path=binary,
            api_ok=api_ok,
            endpoint=self.endpoint,
            models=models,
            selected_model=selected,
            error=error,
        )

    def list_models(self) -> list[OllamaModel]:
        data = self._get_json("/api/tags")
        raw_models = data.get("models", []) if isinstance(data, dict) else []
        return [
            OllamaModel(
                name=str(item.get("name") or item.get("model") or ""),
                size=item.get("size"),
                modified_at=item.get("modified_at"),
            )
            for item in raw_models
            if item.get("name") or item.get("model")
        ]

    def list_models_cli(self) -> list[OllamaModel]:
        if not self.binary_path():
            return []
        proc = subprocess.run(
            ["ollama", "list"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_s,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ollama list failed")
        models = []
        for line in proc.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                models.append(OllamaModel(name=parts[0]))
        return models

    def generate(self, prompt: str, *, model: str | None = None) -> ModelResponse:
        selected = model or self.status().selected_model
        if not selected:
            return ModelResponse(
                provider=self.provider,
                model="",
                content="",
                ok=False,
                error="Nenhum modelo local encontrado no Ollama.",
            )
        try:
            data = self._post_json(
                "/api/generate",
                {"model": selected, "prompt": prompt, "stream": False},
                timeout_s=max(self.timeout_s, 15.0),
            )
            return ModelResponse(
                provider=self.provider,
                model=selected,
                content=str(data.get("response") or ""),
            )
        except Exception as exc:
            return ModelResponse(
                provider=self.provider,
                model=selected,
                content="",
                ok=False,
                error=str(exc),
            )

    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_json(
        self, path: str, payload: dict[str, Any], *, timeout_s: float
    ) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc


def choose_local_model(model_names: list[str]) -> str | None:
    names = [name for name in model_names if name]
    if not names:
        return None
    lower_map = {name.lower(): name for name in names}
    for preferred in LOCAL_MODEL_PREFERENCE:
        if preferred in lower_map:
            return lower_map[preferred]
    for name in names:
        lowered = name.lower()
        if any(token in lowered for token in ("1.5b", "2b", "3b", "mini")):
            return name
    return names[0]
