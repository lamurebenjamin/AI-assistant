import unittest
from unittest.mock import MagicMock

from src.ui.windows.document_composer_controller import DocumentComposerController


class DocumentComposerControllerTests(unittest.TestCase):
    def make_dialog(self):
        dialog = MagicMock()
        dialog.turns = [
            {"question": "first"},
            {"question": "Question audio"},
            {"question": "second"},
        ]
        dialog._pending_forced_tool = None
        dialog._pending_skill_tag = None
        dialog.question.toPlainText.return_value = "new request"
        dialog._take_current_attachments.return_value = ([], "")
        return dialog

    def test_submit_text_delegates_response_creation_and_emits_request(self):
        dialog = self.make_dialog()
        controller = DocumentComposerController(dialog)

        controller._ask_text()

        dialog.begin_response.assert_called_once_with("new request", "", None, [])
        dialog.ask_requested.emit.assert_called_once_with([], "new request", None, None)
        dialog.question.clear.assert_called_once_with()

    def test_prompt_history_excludes_audio_turns(self):
        dialog = self.make_dialog()
        controller = DocumentComposerController(dialog)

        self.assertEqual(controller._prompt_history(), ["first", "second"])

        dialog._prompt_history_index = None
        controller._navigate_prompt_history(-1)

        self.assertEqual(dialog._prompt_history_index, 1)
        dialog.question.setPlainText.assert_called_once_with("second")


if __name__ == "__main__":
    unittest.main()
