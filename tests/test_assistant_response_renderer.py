import unittest
from unittest.mock import MagicMock

from src.ui.windows.assistant_response_renderer import AssistantResponseRenderer


class AssistantResponseRendererTests(unittest.TestCase):
    def make_host(self):
        host = MagicMock()
        host.response_text = "Answer"
        host.current_request_is_audio = False
        host.document_response_active = False
        host.pending_stream_text = ""
        host.is_collapsed = True
        host.split_thinking_and_answer.return_value = ("", "Answer")
        host.markdown_to_html.return_value = "<p>Answer</p>"
        return host

    def test_render_response_updates_host_label(self):
        host = self.make_host()
        renderer = AssistantResponseRenderer(host)

        renderer.render_response()

        host.label.setText.assert_called_once()
        self.assertIn("<p>Answer</p>", host.label.setText.call_args.args[0])

    def test_flush_stream_text_moves_pending_content_into_response(self):
        host = self.make_host()
        host.pending_stream_text = " next"
        renderer = AssistantResponseRenderer(host)

        renderer.flush_stream_text()

        self.assertEqual(host.response_text, "Answer next")
        self.assertEqual(host.pending_stream_text, "")
        host.render_response.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
