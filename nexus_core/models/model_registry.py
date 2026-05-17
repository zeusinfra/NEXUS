from __future__ import annotations

from dataclasses import asdict

from nexus_core.models.cloud_client import cloud_status
from nexus_core.models.ollama_client import OllamaClient


def model_status(endpoint: str = "http://localhost:11434") -> dict:
    ollama = OllamaClient(endpoint).status()
    cloud = cloud_status()
    return {
        "mode": "hybrid",
        "local": {
            **asdict(ollama),
            "ready": ollama.ready,
            "model_count": len(ollama.models),
            "suggestion": None
            if ollama.selected_model
            else "Nenhum modelo local encontrado no Ollama. Rode, por exemplo: ollama pull qwen2.5:3b",
        },
        "cloud": {**asdict(cloud), "ready": cloud.ready},
    }
