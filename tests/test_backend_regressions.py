import unittest

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zeus_core.core_system import _extract_message_content
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

    def test_behavioral_state_ignores_missing_paths(self):
        engine = PatternEngine()
        engine.process_event({"type": "FILE_EVENT", "event": "Create", "path": None})
        engine.process_event({"type": "FILE_EVENT", "event": "WEB_VISIT", "path": "https://example.com"})
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
