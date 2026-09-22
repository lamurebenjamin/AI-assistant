import unittest
from unittest.mock import MagicMock

from src.ui.windows.document_response_controller import DocumentResponseController


class DocumentResponseControllerTests(unittest.TestCase):
    def make_dialog(self):
        dialog = MagicMock()
        dialog.turns = []
        dialog.current_turn_index = -1
        dialog.streaming_response_active = False
        dialog.current_assistant_bubble = None
        dialog.current_thinking_widget = None
        dialog.pending_stream_render = False
        dialog.stream_render_timer.isActive.return_value = False
        return dialog

    def test_begin_response_creates_loading_turn_through_controller(self):
        dialog = self.make_dialog()
        controller = DocumentResponseController(dialog)

        controller.begin_response(
            "Summarize this",
            "<attachment>",
            {"title": "PDF"},
            [{"path": "report.pdf"}],
        )

        self.assertTrue(dialog.streaming_response_active)
        self.assertEqual(dialog.current_turn_index, 0)
        self.assertEqual(dialog.turns[0]["thinking_status"], "Analyse de 1 PDF…")
        self.assertTrue(dialog.turns[0]["loading"])
        dialog._render_conversation.assert_called_once_with()
        dialog.stop_generation_button.setEnabled.assert_called_once_with(True)

    def test_stream_fragments_update_timeline_without_rebuilding_dialog(self):
        dialog = self.make_dialog()
        dialog.turns = [{
            "answer": "",
            "thinking": "",
            "timeline": [],
            "loading": True,
        }]
        dialog.current_turn_index = 0
        controller = DocumentResponseController(dialog)

        controller.append_thinking("thinking")
        controller.append_response("answer")

        turn = dialog.turns[0]
        self.assertEqual(turn["thinking"], "thinking")
        self.assertEqual(turn["answer"], "answer")
        self.assertEqual(
            [item["type"] for item in turn["timeline"]],
            ["thinking", "response"],
        )
        self.assertFalse(turn["loading"])
        self.assertTrue(dialog.pending_stream_render)
        dialog.stream_render_timer.start.assert_called()

    def test_toggle_layout_callback_is_exposed_by_dialog_facade(self):
        from src.ui.windows.document_dialog import DocumentDialog

        controller = MagicMock()
        facade = DocumentDialog.__new__(DocumentDialog)
        facade.response_controller = controller
        scroll_bar = MagicMock()

        facade._finish_toggle_layout(scroll_bar, 12)

        controller._finish_toggle_layout.assert_called_once_with(scroll_bar, 12)


if __name__ == "__main__":
    unittest.main()
