import unittest

from PySide6.QtWidgets import (
    QApplication,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui.widgets.tool_call_step import ToolCallStepWidget
from src.ui.widgets.tool_call_widget import ToolExecutionGroupWidget
from src.ui.windows.document_conversation_renderer import DocumentConversationRenderer


class DocumentTimelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_dialog(self, turn):
        host = QWidget()
        host.resize(900, 500)
        conversation_widget = QWidget(host)
        conversation_layout = QVBoxLayout(conversation_widget)
        conversation_layout.setContentsMargins(0, 0, 0, 0)

        response = QScrollArea(host)
        response.setWidgetResizable(True)
        response.setWidget(conversation_widget)
        response_holder = QWidget(host)
        turn_navigation = QWidget(host)
        turn_navigation_layout = QVBoxLayout(turn_navigation)

        class DialogFacade:
            FONT_SIZE_OFFSET = 0
            host = None
            current_turn_index = 0
            current_assistant_bubble = None
            current_thinking_widget = None

            def __init__(self):
                self.turns = [turn]
                self._turn_rows = []
                self._turn_navigation_buttons = []

            def _clear_conversation_widgets(self):
                while conversation_layout.count():
                    item = conversation_layout.takeAt(0)
                    if item.widget() is not None:
                        item.widget().deleteLater()

            def _clear_turn_navigation(self):
                while turn_navigation_layout.count():
                    item = turn_navigation_layout.takeAt(0)
                    if item.widget() is not None:
                        item.widget().deleteLater()

            def _answer_without_sources(self, answer):
                return answer

            def _open_source_link(self, _url):
                return None

            def _navigate_to_turn(self, _index):
                return None

            def _on_tool_widget_toggled(self):
                return None

            def _sync_conversation_widget_height(self):
                return None

            def _update_height(self):
                return None

            def _refresh_stream_view(self):
                return None

            def _update_turn_navigation_visibility(self):
                return None

        dialog = DialogFacade()
        dialog.conversation_widget = conversation_widget
        dialog.conversation_layout = conversation_layout
        dialog.response = response
        dialog.response_holder = response_holder
        dialog.turn_navigation = turn_navigation
        dialog.turn_navigation_layout = turn_navigation_layout
        dialog.width = host.width
        dialog._root = host
        return dialog

    def test_renderer_builds_complete_mocked_tool_timeline_without_network(self):
        turn = {
            "question": "Analyse le document",
            "answer": "Voici le résultat.",
            "thinking": "",
            "loading": False,
            "tools_collapsed": False,
            "timeline": [
                {
                    "type": "thinking",
                    "text": "Je vérifie le fichier.",
                },
                {
                    "type": "tools",
                    "tools": [
                        {
                            "name": "read_file",
                            "status": "completed",
                            "arguments": '{"path": "rapport.txt"}',
                            "result": '{"content": "Données extraites"}',
                            "skill_name": "documents",
                            "tool_title": "Lire le fichier",
                            "expanded": True,
                        },
                        {
                            "name": "create_docx",
                            "status": "error",
                            "arguments": '{"filename": "sortie.docx"}',
                            "result": "Permission refusée",
                            "skill_name": "docx",
                            "tool_title": "Créer le document",
                            "expanded": True,
                        },
                    ],
                },
                {
                    "type": "response",
                    "text": "Voici le résultat.",
                },
            ],
        }
        dialog = self.make_dialog(turn)
        renderer = DocumentConversationRenderer(dialog)

        renderer.render()
        self.app.processEvents()

        groups = dialog.conversation_widget.findChildren(ToolExecutionGroupWidget)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        steps = group.steps_container.findChildren(ToolCallStepWidget)
        self.assertEqual(len(steps), 2)
        self.assertIn("Lire le fichier", steps[0].action_label.text())
        self.assertIn("Failed", steps[1].action_label.text())
        self.assertFalse(steps[0].details_panel.isHidden())
        self.assertFalse(steps[1].details_panel.isHidden())
        dialog._root.close()

    def test_error_tool_response_is_rendered_without_http_client(self):
        turn = {
            "question": "Exécute l'outil",
            "answer": "",
            "loading": False,
            "tools_collapsed": False,
            "timeline": [
                {
                    "type": "tools",
                    "tools": [
                        {
                            "name": "run_command",
                            "status": "error",
                            "arguments": '{"command": "echo test"}',
                            "result": "Commande interrompue",
                            "expanded": True,
                        }
                    ],
                }
            ],
            "error": "L'outil a échoué.",
        }
        dialog = self.make_dialog(turn)
        DocumentConversationRenderer(dialog).render()
        self.app.processEvents()

        step = dialog.conversation_widget.findChild(ToolCallStepWidget)
        self.assertIsNotNone(step)
        self.assertEqual(step.tool_info["result"], "Commande interrompue")
        self.assertIn("Erreur", [label.text() for label in step.findChildren(type(step.action_label))])
        dialog._root.close()


if __name__ == "__main__":
    unittest.main()
