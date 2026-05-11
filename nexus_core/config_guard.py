from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


TRUE_VALUES = {"1", "true", "yes", "on"}
PRODUCTION_ENVS = {"prod", "production"}
INSECURE_JWT_SECRETS = {
    "super_secret_nexus_key_998877",
    "dev_only_change_me_nexus_jwt_secret",
    "replace_with_at_least_32_random_chars",
}


@dataclass(frozen=True)
class LanSecurityConfig:
    allow_lan: bool
    lan_auth_enabled: bool
    lan_token: str
    bind_host: str


def env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in TRUE_VALUES


def nexus_env() -> str:
    return (
        os.getenv("NEXUS_ENV", os.getenv("APP_ENV", "local")).strip().lower() or "local"
    )


def is_production() -> bool:
    return nexus_env() in PRODUCTION_ENVS


def validate_jwt_secret(
    secret: str, *, allow_insecure_dev_secret: bool, production: bool | None = None
) -> str:
    production = is_production() if production is None else production
    secret = (secret or "").strip()
    if not secret:
        if allow_insecure_dev_secret and not production:
            return "dev_only_change_me_nexus_jwt_secret"
        raise RuntimeError(
            "NEXUS_JWT_SECRET must be set. Use NEXUS_ALLOW_INSECURE_DEV_SECRET=1 only for local development."
        )
    if secret in INSECURE_JWT_SECRETS:
        if allow_insecure_dev_secret and not production:
            return secret
        raise RuntimeError("NEXUS_JWT_SECRET is insecure. Set a strong secret.")
    if len(secret) < 32:
        if allow_insecure_dev_secret and not production:
            return secret
        raise RuntimeError("NEXUS_JWT_SECRET must be at least 32 characters.")
    return secret


def remote_auth_required(*, allow_lan: bool, bind_host: str) -> bool:
    return allow_lan or bind_host not in {"127.0.0.1", "::1", "localhost"}


def validate_lan_security(config: LanSecurityConfig) -> None:
    if not remote_auth_required(allow_lan=config.allow_lan, bind_host=config.bind_host):
        return
    if not config.lan_auth_enabled:
        raise RuntimeError(
            "NEXUS_LAN_AUTH=1 is required when remote access is enabled."
        )
    if not config.lan_token or len(config.lan_token) < 16:
        raise RuntimeError(
            "NEXUS_LAN_TOKEN must be set (>=16 chars) when remote access is enabled."
        )


def validate_llm_config() -> None:
    provider = os.getenv("NEXUS_LLM_PROVIDER", "").strip().lower()
    if provider and provider not in {"ollama", "openai", "gemini"}:
        raise RuntimeError("NEXUS_LLM_PROVIDER must be one of: ollama, openai, gemini.")

    if provider == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY must be set when NEXUS_LLM_PROVIDER=openai.")

    if provider == "gemini" and not os.getenv("GEMINI_API_KEY", "").strip():
        raise RuntimeError("GEMINI_API_KEY must be set when NEXUS_LLM_PROVIDER=gemini.")

    llm_url = os.getenv("NEXUS_LLM_URL", "").strip()
    parsed = urlparse(llm_url)
    using_ollama_cloud_api = provider == "ollama" and parsed.netloc.endswith(
        "ollama.com"
    )
    if using_ollama_cloud_api and not (
        os.getenv("OLLAMA_API_KEY", "").strip()
        or os.getenv("NEXUS_LLM_API_KEY", "").strip()
    ):
        raise RuntimeError(
            "OLLAMA_API_KEY or NEXUS_LLM_API_KEY must be set when using the hosted Ollama API."
        )


def validate_startup_config(*, lan: LanSecurityConfig) -> None:
    validate_lan_security(lan)
    validate_llm_config()


def build_config_diagnostics(*, lan: LanSecurityConfig) -> dict:
    provider = os.getenv("NEXUS_LLM_PROVIDER", "").strip().lower() or "auto"
    llm_url = os.getenv("NEXUS_LLM_URL", "").strip()
    parsed = urlparse(llm_url)
    hosted_ollama_api = provider == "ollama" and parsed.netloc.endswith("ollama.com")
    remote_required = remote_auth_required(
        allow_lan=lan.allow_lan, bind_host=lan.bind_host
    )

    warnings: list[str] = []
    if is_production() and env_flag("NEXUS_ALLOW_INSECURE_DEV_SECRET", "0"):
        warnings.append("insecure_dev_secret_enabled")
    if remote_required and not lan.lan_auth_enabled:
        warnings.append("remote_auth_disabled")
    if remote_required and len(lan.lan_token or "") < 16:
        warnings.append("lan_token_missing_or_weak")
    if hosted_ollama_api and not (
        os.getenv("OLLAMA_API_KEY", "").strip()
        or os.getenv("NEXUS_LLM_API_KEY", "").strip()
    ):
        warnings.append("ollama_hosted_api_missing_key")

    return {
        "env": nexus_env(),
        "production": is_production(),
        "llm_provider": provider,
        "remote_auth_required": remote_required,
        "lan_auth_enabled": bool(lan.lan_auth_enabled),
        "hosted_ollama_api": hosted_ollama_api,
        "warnings": warnings,
    }
