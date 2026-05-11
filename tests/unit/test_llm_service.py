import unittest
from unittest.mock import patch

from nexus_core.llm_service import LLMService


class LLMServiceTests(unittest.TestCase):
    def test_connectivity_test_returns_ok_for_normal_reply(self):
        service = LLMService(
            get_status=lambda: {"provider": "test"},
            call_llm=lambda messages: "ZEUS LLM OK",
        )

        with patch("nexus_core.llm_service.log_event"):
            result = service.test_connectivity()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"]["provider"], "test")
        self.assertIn("ZEUS LLM OK", result["reply"])

    def test_connectivity_test_marks_provider_error_as_not_ok(self):
        service = LLMService(
            get_status=lambda: {"provider": "test"},
            call_llm=lambda messages: "Error: unauthorized",
        )

        with patch("nexus_core.llm_service.log_event"):
            result = service.test_connectivity()

        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
