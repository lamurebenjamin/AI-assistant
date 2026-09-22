import base64

from PySide6.QtCore import QUrl

from src.ui.windows.conversation_controller import ConversationController


class _Host:
    def __init__(self):
        self.sources = []

    def open_document_source(self, filename, page):
        self.sources.append((filename, page))


class _Dialog:
    def __init__(self):
        self.host = _Host()
        self.turns = [{"sources_html": ""}]
        self.rendered = 0
        self.source_html_calls = []

    def _render_conversation_impl(self):
        self.rendered += 1

    def _add_sources_html(self, answer, documents):
        self.source_html_calls.append((answer, documents))
        return "<source>"


def test_controller_delegates_rendering_and_source_capture_updates():
    dialog = _Dialog()
    controller = ConversationController(dialog)

    controller.render()
    controller.show_source_captures("answer", ["document.pdf"])

    assert dialog.rendered == 2
    assert dialog.turns[-1]["sources_html"] == "<source>"
    assert dialog.source_html_calls == [("answer", ["document.pdf"])]


def test_controller_preserves_source_link_navigation():
    dialog = _Dialog()
    controller = ConversationController(dialog)
    token = base64.urlsafe_b64encode("document.pdf".encode()).decode().rstrip("=")

    controller.open_source_link(QUrl(f"source:3:{token}"))

    assert dialog.host.sources == [("document.pdf", 3)]
