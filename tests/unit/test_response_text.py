import unittest

from zeus_core.response_text import display_text, pango_markup, speech_text


class ResponseTextTests(unittest.TestCase):
    def test_speech_text_removes_markdown_control_signs(self):
        raw = "# Plano\n- **Reiniciar** `backend`\n- Ver logs -> corrigir"

        spoken = speech_text(raw)

        self.assertNotIn("#", spoken)
        self.assertNotIn("*", spoken)
        self.assertNotIn("`", spoken)
        self.assertIn("Plano", spoken)
        self.assertIn("Reiniciar backend", spoken)
        self.assertIn("Ver logs para corrigir", spoken)

    def test_display_text_keeps_readable_list_without_raw_markdown(self):
        raw = "## Status\n- **Notion** conectado"

        rendered = display_text(raw)

        self.assertIn("Status", rendered)
        self.assertIn("• Notion conectado", rendered)
        self.assertNotIn("##", rendered)
        self.assertNotIn("**", rendered)

    def test_display_text_replaces_visual_arrows(self):
        self.assertEqual(display_text("logs -> corrigir"), "logs para corrigir")

    def test_pango_markup_formats_bold_without_exposing_markdown(self):
        markup = pango_markup("**Pronto** para operar")

        self.assertIn("<b>Pronto</b>", markup)
        self.assertNotIn("**", markup)


if __name__ == "__main__":
    unittest.main()
