import unittest
from unittest.mock import patch

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zeus_core.core_system import _extract_message_content
from zeus_core import core_system
from zeus_core.health_status import build_external_watcher_status, build_watcher_status
from pattern_engine import PatternEngine
import web_gui


class BackendRegressionTests(unittest.TestCase):
    def test_extract_message_content_supports_openai_shape(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": "resposta ok",
                    }
                }
            ]
        }
        self.assertEqual(_extract_message_content(payload), "resposta ok")

    def test_openai_status_does_not_expose_api_key(self):
        original_provider = core_system.LLM_PROVIDER
        original_key = core_system.OPENAI_API_KEY
        original_model = core_system.OPENAI_MODEL
        try:
            core_system.LLM_PROVIDER = "openai"
            core_system.OPENAI_API_KEY = "sk-test-secret"
            core_system.OPENAI_MODEL = "gpt-4o-mini"

            status = core_system.get_llm_status()

            self.assertEqual(status["provider"], "openai")
            self.assertEqual(status["model"], "gpt-4o-mini")
            self.assertTrue(status["configured"])
            self.assertNotIn("api_key", status)
            self.assertNotIn("sk-test-secret", str(status))
        finally:
            core_system.LLM_PROVIDER = original_provider
            core_system.OPENAI_API_KEY = original_key
            core_system.OPENAI_MODEL = original_model

    def test_openai_error_maps_insufficient_quota(self):
        class Response:
            status_code = 429
            text = '{"error":{"code":"insufficient_quota"}}'

            def json(self):
                return {
                    "error": {"code": "insufficient_quota", "message": "quota exceeded"}
                }

        msg = core_system._format_openai_error(Response())
        self.assertIn("billing", msg.lower())
        self.assertIn("quota", msg.lower())

    def test_ollama_cloud_unauthorized_error_mentions_auth_options(self):
        class Response:
            status_code = 401
            text = "Unauthorized"

        msg = core_system._format_ollama_error(Response())
        self.assertIn("Ollama Cloud", msg)
        self.assertIn("ollama signin", msg)
        self.assertIn("OLLAMA_API_KEY", msg)

    def test_watcher_status_reports_offline_without_process(self):
        status = build_watcher_status(None, None, None)
        self.assertEqual(status["status"], "offline")
        self.assertIsNone(status["pid"])

    def test_external_watcher_status_detects_process(self):
        class Proc:
            info = {
                "pid": 1234,
                "cmdline": ["/repo/watcher_rs/target/release/watcher_rs"],
                "create_time": time.time() - 5,
            }

        with patch(
            "zeus_core.health_status.psutil.process_iter", return_value=[Proc()]
        ):
            with patch("zeus_core.health_status._watcher_port_open", return_value=True):
                status = build_external_watcher_status("/repo", port=8081)

        self.assertEqual(status["status"], "online")
        self.assertEqual(status["pid"], 1234)
        self.assertEqual(status["mode"], "external")
        self.assertTrue(status["port_open"])

    def test_external_watcher_status_reports_offline_when_absent(self):
        with patch("zeus_core.health_status.psutil.process_iter", return_value=[]):
            with patch(
                "zeus_core.health_status._watcher_port_open", return_value=False
            ):
                status = build_external_watcher_status("/repo", port=8081)

        self.assertEqual(status["status"], "offline")
        self.assertIsNone(status["pid"])

    def test_external_watcher_status_handles_restarts(self):
        class Proc1:
            info = {
                "pid": 1111,
                "cmdline": ["/repo/watcher_rs/target/release/watcher_rs"],
                "create_time": time.time() - 100,
            }

        class Proc2:
            info = {
                "pid": 2222,
                "cmdline": ["/repo/watcher_rs/target/release/watcher_rs"],
                "create_time": time.time() - 5,
            }

        with patch("zeus_core.health_status._watcher_port_open", return_value=True):
            # Simulando a primeira execução
            with patch(
                "zeus_core.health_status.psutil.process_iter", return_value=[Proc1()]
            ):
                status1 = build_external_watcher_status("/repo", port=8081)
                self.assertEqual(status1["pid"], 1111)
                self.assertGreaterEqual(status1["uptime_s"], 99)
                self.assertLessEqual(status1["uptime_s"], 101)

            # Simulando restart (novo PID, tempo de atividade resetado)
            with patch(
                "zeus_core.health_status.psutil.process_iter", return_value=[Proc2()]
            ):
                status2 = build_external_watcher_status("/repo", port=8081)
                self.assertEqual(status2["pid"], 2222)
                self.assertGreaterEqual(status2["uptime_s"], 4)
                self.assertLessEqual(status2["uptime_s"], 6)

    def test_behavioral_state_ignores_missing_paths(self):
        engine = PatternEngine()
        engine.process_event({"type": "FILE_EVENT", "event": "Create", "path": None})
        engine.process_event(
            {"type": "FILE_EVENT", "event": "WEB_VISIT", "path": "https://example.com"}
        )
        self.assertEqual(engine.analyze_behavioral_state(), "BALANCED")

    def test_ensure_memory_entry_normalizes_invalid_memory_shapes(self):
        original_memory = web_gui.synaptic_memory
        try:
            web_gui.synaptic_memory = {
                "/tmp/file.py": {"weight": "7", "connections": ["/tmp/other.py"]},
                "/tmp/broken.py": "invalid",
            }
            valid = web_gui.ensure_memory_entry("/tmp/file.py")
            broken = web_gui.ensure_memory_entry("/tmp/broken.py")

            self.assertEqual(valid["weight"], 7)
            self.assertEqual(valid["connections"], {"/tmp/other.py"})
            self.assertEqual(broken["weight"], 0)
            self.assertEqual(broken["connections"], set())
        finally:
            web_gui.synaptic_memory = original_memory

    def test_build_memory_summary_reports_recall_and_density(self):
        original_memory = web_gui.synaptic_memory
        try:
            web_gui.synaptic_memory = {
                "/tmp/a.py": {"weight": 8, "connections": {"/tmp/b.py", "/tmp/c.py"}},
                "/tmp/b.py": {"weight": 4, "connections": {"/tmp/a.py"}},
            }
            summary = web_gui.build_memory_summary()
            self.assertEqual(summary["learned_paths"], 2)
            self.assertEqual(summary["connection_total"], 3)
            self.assertEqual(summary["hottest_path"], "/tmp/a.py")
            self.assertGreater(summary["recall_index"], 0)
            self.assertGreater(summary["memory_density"], 0)
        finally:
            web_gui.synaptic_memory = original_memory


if __name__ == "__main__":
    unittest.main()
