"""Tests pour les fonctions helpers de feuilles de style centralisées.

Règle SST : toute couleur hexadécimale raw (#...) ne doit jamais être codée
en dur dans les composants UI — seuls les tokens de design_tokens.py et les
helpers de stylesheet.py sont autorisés.

Exécution
---------
    python -m unittest tests.test_stylesheet_helpers -v
"""

import re
import unittest


class TestStylesheetHelpers(unittest.TestCase):
    """Vérifie que les helpers retournent des chaînes QSS valides et cohérentes."""

    def _import_helpers(self):
        """Importe les helpers sans QApplication."""
        from src.ui import stylesheet as ss
        return ss

    def test_skill_tag_title_contains_color(self):
        ss = self._import_helpers()
        result = ss.qss_skill_tag_title(font_size=12, weight=600)
        self.assertIn("color:", result)
        self.assertIn("font-size: 12px", result)
        self.assertIn("font-weight: 600", result)

    def test_skill_tag_title_custom_color(self):
        ss = self._import_helpers()
        result = ss.qss_skill_tag_title(color="#aabbcc", font_size=11)
        self.assertIn("#aabbcc", result)

    def test_skill_tag_frame_targets_objectname(self):
        ss = self._import_helpers()
        result = ss.qss_skill_tag_frame()
        self.assertIn("QFrame#SkillTag", result)
        self.assertIn("border:", result)
        self.assertIn("border-radius:", result)

    def test_timeline_connector_has_background(self):
        ss = self._import_helpers()
        result = ss.qss_timeline_connector()
        self.assertIn("background:", result)

    def test_timeline_header_title_injects_color(self):
        ss = self._import_helpers()
        result = ss.qss_timeline_header_title("#ff0000")
        self.assertIn("#ff0000", result)
        self.assertIn("font-weight: 500", result)

    def test_voice_recording_indicator_labels(self):
        ss = self._import_helpers()
        result = ss.qss_voice_recording_indicator()
        self.assertIn("VoiceText", result)
        self.assertIn("VoiceClock", result)
        self.assertIn("AcrylicPanel", result)

    def test_status_label_italic(self):
        ss = self._import_helpers()
        result = ss.qss_status_label("#fff", "12px", weight=400, italic=True)
        self.assertIn("italic", result)
        self.assertIn("font-weight: 400", result)

    def test_status_label_not_italic(self):
        ss = self._import_helpers()
        result = ss.qss_status_label("#fff", "12px", italic=False)
        self.assertIn("normal", result)

    def test_shimmer_status_label_offset(self):
        ss = self._import_helpers()
        import src.ui.design_tokens as t
        base_size = int(t.SIZE_SM.rstrip("px"))
        result_0 = ss.qss_shimmer_status_label(0)
        result_2 = ss.qss_shimmer_status_label(2)
        self.assertIn(f"font-size: {base_size}px", result_0)
        self.assertIn(f"font-size: {base_size + 2}px", result_2)

    def test_slash_icon_label_has_font_size(self):
        ss = self._import_helpers()
        result = ss.qss_slash_icon_label()
        self.assertIn("font-size: 14px", result)

    def test_scrollbar_hidden_horizontal_is_string(self):
        ss = self._import_helpers()
        result = ss.qss_scrollbar_hidden_horizontal()
        self.assertIsInstance(result, str)
        self.assertIn("horizontal", result)


class TestStylesheetSingleSource(unittest.TestCase):
    """Vérifie que les composants utilisent les helpers, non du QSS inline."""

    def _read_source(self, relative_path: str) -> str:
        from pathlib import Path
        root = Path(__file__).parent.parent
        return (root / relative_path).read_text(encoding="utf-8")

    def test_skill_tag_no_inline_hex_color(self):
        """skill_tag.py ne doit pas contenir de couleur hex brute dans setStyleSheet."""
        src = self._read_source("src/ui/widgets/skill_tag.py")
        inline_hex = re.findall(r'setStyleSheet\([^)]*#[0-9a-fA-F]{3,8}', src)
        self.assertEqual(
            [], inline_hex,
            "Couleur hex brute détectée dans setStyleSheet() de skill_tag.py.\n"
            "Utiliser qss_skill_tag_title() / qss_skill_tag_frame() à la place."
        )

    def test_recording_indicator_uses_helper(self):
        """recording_indicator.py doit importer qss_voice_recording_indicator."""
        src = self._read_source("src/ui/widgets/recording_indicator.py")
        self.assertIn("qss_voice_recording_indicator", src)

    def test_status_label_uses_helper(self):
        """status_label.py doit importer qss_status_label."""
        src = self._read_source("src/ui/widgets/status_label.py")
        self.assertIn("qss_status_label", src)

    def test_timeline_header_uses_helper(self):
        """timeline_header.py doit importer qss_timeline_header_title."""
        src = self._read_source("src/ui/widgets/timeline_header.py")
        self.assertIn("qss_timeline_header_title", src)

    def test_document_conversation_renderer_uses_helper(self):
        """document_conversation_renderer.py doit importer qss_shimmer_status_label."""
        src = self._read_source("src/ui/windows/document_conversation_renderer.py")
        self.assertIn("qss_shimmer_status_label", src)


if __name__ == "__main__":
    unittest.main()
