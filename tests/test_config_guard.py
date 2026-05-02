import os
import unittest
from unittest.mock import patch

from zeus_core.config_guard import (
    LanSecurityConfig,
    build_config_diagnostics,
    validate_jwt_secret,
    validate_lan_security,
    validate_llm_config,
)


class ConfigGuardTests(unittest.TestCase):
    def test_rejects_missing_jwt_secret_in_production(self):
        with self.assertRaisesRegex(RuntimeError, "ZEUS_JWT_SECRET"):
            validate_jwt_secret("", allow_insecure_dev_secret=True, production=True)

    def test_allows_dev_secret_only_outside_production(self):
        secret = validate_jwt_secret("", allow_insecure_dev_secret=True, production=False)
        self.assertEqual(secret, "dev_only_change_me_zeus_jwt_secret")

    def test_rejects_remote_bind_without_lan_auth(self):
        config = LanSecurityConfig(
            allow_lan=False,
            lan_auth_enabled=False,
            lan_token="",
            bind_host="0.0.0.0",
        )
        with self.assertRaisesRegex(RuntimeError, "ZEUS_LAN_AUTH"):
            validate_lan_security(config)

    def test_rejects_remote_bind_without_strong_lan_token(self):
        config = LanSecurityConfig(
            allow_lan=True,
            lan_auth_enabled=True,
            lan_token="short",
            bind_host="0.0.0.0",
        )
        with self.assertRaisesRegex(RuntimeError, "ZEUS_LAN_TOKEN"):
            validate_lan_security(config)

    def test_allows_local_bind_without_lan_token(self):
        config = LanSecurityConfig(
            allow_lan=False,
            lan_auth_enabled=False,
            lan_token="",
            bind_host="127.0.0.1",
        )
        validate_lan_security(config)

    def test_openai_provider_requires_key(self):
        with patch.dict(os.environ, {"ZEUS_LLM_PROVIDER": "openai", "OPENAI_API_KEY": ""}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                validate_llm_config()

    def test_hosted_ollama_api_requires_api_key(self):
        env = {
            "ZEUS_LLM_PROVIDER": "ollama",
            "ZEUS_LLM_URL": "https://ollama.com/api/chat",
            "OLLAMA_API_KEY": "",
            "ZEUS_LLM_API_KEY": "",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OLLAMA_API_KEY"):
                validate_llm_config()

    def test_config_diagnostics_do_not_expose_secret_values(self):
        env = {
            "ZEUS_ENV": "prod",
            "ZEUS_ALLOW_INSECURE_DEV_SECRET": "1",
            "ZEUS_LLM_PROVIDER": "ollama",
            "ZEUS_LLM_URL": "https://ollama.com/api/chat",
            "OLLAMA_API_KEY": "secret-token",
        }
        config = LanSecurityConfig(
            allow_lan=True,
            lan_auth_enabled=True,
            lan_token="secret-lan-token-value",
            bind_host="0.0.0.0",
        )
        with patch.dict(os.environ, env, clear=True):
            diagnostics = build_config_diagnostics(lan=config)

        self.assertTrue(diagnostics["production"])
        self.assertEqual(diagnostics["env"], "prod")
        self.assertNotIn("secret-token", str(diagnostics))
        self.assertNotIn("secret-lan-token-value", str(diagnostics))


if __name__ == "__main__":
    unittest.main()
