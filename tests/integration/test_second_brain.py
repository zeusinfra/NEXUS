import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zeus_core.cognitive.classifier import decide_action
from zeus_core.cognitive.context_engine import _area_from_tags
from zeus_core.events.sync_engine import _format_operational_status_for_notion
from zeus_core.integrations import notion
from zeus_core.integrations.obsidian import (
    extract_internal_links,
    extract_tags,
    read_note,
)


class SecondBrainTests(unittest.TestCase):
    def test_classifier_routes_to_notion_and_linear(self):
        decision = decide_action({"tags": ["#project", "#bug", "#security"]})

        self.assertEqual(decision["action"], "both")
        self.assertEqual(decision["priority"], "high")
        self.assertIn("security", decision["labels"])

    def test_obsidian_note_parser_extracts_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "Roadmap.md"
            note.write_text("# Roadmap\n#project [[ZEUS]]\nTexto", encoding="utf-8")

            parsed = read_note(str(note))

        self.assertEqual(parsed["title"], "Roadmap")
        self.assertIn("#project", parsed["tags"])
        self.assertIn("ZEUS", parsed["internal_links"])
        self.assertTrue(parsed["hash"])

    def test_tag_extraction_ignores_markdown_headers(self):
        tags = extract_tags("# Heading\ntexto #to-linear #performance")

        self.assertNotIn("#Heading", tags)
        self.assertIn("#to-linear", tags)
        self.assertIn("#performance", tags)

    def test_internal_link_extraction(self):
        self.assertCountEqual(extract_internal_links("[[A]] e [[B]]"), ["A", "B"])

    def test_disabled_integrations_do_not_call_network(self):
        import zeus_core.integrations.linear as linear
        import zeus_core.integrations.notion as notion

        with patch.dict(
            os.environ,
            {"ZEUS_ENABLE_NOTION": "0", "ZEUS_ENABLE_LINEAR": "0"},
            clear=False,
        ):
            notion = importlib.reload(notion)
            linear = importlib.reload(linear)

            self.assertEqual(
                notion.create_notion_page("T", "C", [], "x")["error"], "Disabled"
            )
            self.assertEqual(
                linear.create_linear_issue("T", "D", [], "medium", "x")["error"],
                "Disabled",
            )

        importlib.reload(notion)
        importlib.reload(linear)

    def test_env_example_keeps_sync_engine_opt_in(self):
        env_example = Path(".env.example").read_text(encoding="utf-8")

        self.assertIn("ZEUS_ENABLE_SECOND_BRAIN=0", env_example)
        self.assertIn("ZEUS_ENABLE_SECOND_BRAIN_SYNC_ENGINE=0", env_example)
        self.assertIn("ZEUS_ENABLE_NOTION_AUTO_SYNC=0", env_example)
        self.assertIn("ZEUS_ENABLE_LINEAR_AUTO_SYNC=0", env_example)

    def test_context_area_mapping_links_information_to_domain(self):
        self.assertEqual(_area_from_tags('["#bug", "#infra"]'), "tarefa/operação")
        self.assertEqual(_area_from_tags('["#to-notion"]'), "documentação")
        self.assertEqual(_area_from_tags('["#zeus-memory"]'), "memória")

    def test_operational_status_page_formats_sync_data(self):
        content = _format_operational_status_for_notion(
            {
                "total_events": 3,
                "pending": 1,
                "processed": 2,
                "error": 0,
                "total_sync_ops": 8,
                "last_sync_op": "2026-05-04 10:00:00",
            }
        )

        self.assertIn("ZEUS — Estado Operacional", content)
        self.assertIn("Eventos totais: 3", content)
        self.assertIn("Operações de sync registradas: 8", content)

    def test_notion_page_properties_follow_database_schema(self):
        schema = {
            "Title": {"type": "title"},
            "Tags": {"type": "multi_select"},
            "Notes": {"type": "rich_text"},
        }

        with patch.object(notion, "_get_database_properties", return_value=schema):
            properties = notion._build_page_properties("ZEUS", ["#memory"], "memory.md")

        self.assertIn("Title", properties)
        self.assertIn("Tags", properties)
        self.assertNotIn("Source Path", properties)


if __name__ == "__main__":
    unittest.main()
