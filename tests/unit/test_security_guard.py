import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from nexus_core.config_guard import LanSecurityConfig
from nexus_core.security_guard import (
    extract_bearer_token,
    is_trusted_host,
    require_lan_token_for_request,
    require_lan_token_for_socketio,
)


class SecurityGuardTests(unittest.TestCase):
    def test_extract_bearer_token_accepts_plain_and_bearer(self):
        self.assertEqual(extract_bearer_token("Bearer abc123"), "abc123")
        self.assertEqual(extract_bearer_token("abc123"), "abc123")
        self.assertIsNone(extract_bearer_token(""))

    def test_trusted_host_allows_loopback_and_lan_only_when_enabled(self):
        self.assertTrue(is_trusted_host("127.0.0.1", allow_lan=False))
        self.assertFalse(is_trusted_host("192.168.1.10", allow_lan=False))
        self.assertTrue(is_trusted_host("192.168.1.10", allow_lan=True))

    def test_request_requires_token_for_remote_lan_client(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="192.168.1.10"),
            headers={},
            query_params={},
        )
        lan = LanSecurityConfig(
            allow_lan=True,
            lan_auth_enabled=True,
            lan_token="valid-token-12345",
            bind_host="0.0.0.0",
        )
        with self.assertRaises(HTTPException) as ctx:
            require_lan_token_for_request(request, lan=lan)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_request_accepts_header_token_for_remote_lan_client(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="192.168.1.10"),
            headers={"authorization": "Bearer valid-token-12345"},
            query_params={},
        )
        lan = LanSecurityConfig(
            allow_lan=True,
            lan_auth_enabled=True,
            lan_token="valid-token-12345",
            bind_host="0.0.0.0",
        )
        require_lan_token_for_request(request, lan=lan)

    def test_socketio_accepts_query_token_for_remote_lan_client(self):
        environ = {
            "REMOTE_ADDR": "192.168.1.10",
            "QUERY_STRING": "token=valid-token-12345",
        }
        lan = LanSecurityConfig(
            allow_lan=True,
            lan_auth_enabled=True,
            lan_token="valid-token-12345",
            bind_host="0.0.0.0",
        )
        self.assertTrue(require_lan_token_for_socketio(environ, None, lan=lan))

    def test_socketio_rejects_missing_token_for_remote_lan_client(self):
        environ = {"REMOTE_ADDR": "192.168.1.10", "QUERY_STRING": ""}
        lan = LanSecurityConfig(
            allow_lan=True,
            lan_auth_enabled=True,
            lan_token="valid-token-12345",
            bind_host="0.0.0.0",
        )
        self.assertFalse(require_lan_token_for_socketio(environ, None, lan=lan))


if __name__ == "__main__":
    unittest.main()
