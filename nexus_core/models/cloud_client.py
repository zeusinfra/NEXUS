from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudStatus:
    provider: str
    model: str
    enabled: bool
    api_key_env: str
    api_key_present: bool

    @property
    def ready(self) -> bool:
        if self.provider in {"ollama", "ollama-cloud", "local-ollama"}:
            return self.enabled
        return self.enabled and self.api_key_present


def cloud_status() -> CloudStatus:
    provider = os.getenv(
        "NEXUS_CLOUD_PROVIDER", os.getenv("NEXUS_LLM_PROVIDER", "ollama")
    )
    model = os.getenv(
        "NEXUS_CLOUD_MODEL", os.getenv("OPENAI_MODEL", "gemma4:31b-cloud")
    )
    api_key_env = os.getenv("NEXUS_CLOUD_API_KEY_ENV", "NEXUS_CLOUD_API_KEY")
    enabled = os.getenv("NEXUS_CLOUD_ENABLED", "1").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return CloudStatus(
        provider=provider,
        model=model,
        enabled=enabled,
        api_key_env=api_key_env,
        api_key_present=bool(os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY")),
    )
