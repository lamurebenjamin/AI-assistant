import unittest

from src.ui.stylesheet import qss_document_dialog, qss_tool_call_step
from src.ui.stylesheet_document import qss_document_preview_dialog
from src.ui.widgets.timeline_header import ChevronLabel, CollapsibleHeader


class ExtractedUiComponentsTests(unittest.TestCase):
    def test_document_stylesheet_exports_remain_compatible(self):
        self.assertIn("QFrame#DocPanel", qss_document_dialog())
        self.assertIn("QFrame#ToolCallStep", qss_tool_call_step())
        self.assertIn("QDialog", qss_document_preview_dialog())

    def test_timeline_header_symbols_are_available_from_new_module(self):
        self.assertTrue(issubclass(ChevronLabel, object))
        self.assertTrue(issubclass(CollapsibleHeader, object))


if __name__ == "__main__":
    unittest.main()
