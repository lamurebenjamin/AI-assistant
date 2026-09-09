# -*- coding: utf-8 -*-
"""Script de test pour le menu des skills et ToolCallWidget."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
from src.ui.icons import initialize_icons
initialize_icons()

from src.ui.widgets.tool_call_widget import ToolCallWidget
from src.ui.windows.document_dialog import DocumentDialog

# 1. Test ToolCallWidget
tool_data = {
    'name': 'create_pdf',
    'status': 'running',
    'arguments': '{"filename": "test.pdf", "title": "Test PDF", "paragraphs": ["Hello"]}',
    'result': '',
    'expanded': False
}
w = ToolCallWidget(tool_data)
assert w.status_badge.text() == 'En cours...', f"Bad status text: {w.status_badge.text()}"
w._toggle_expanded()
assert tool_data['expanded'] is True
assert not w.details_panel.isHidden()
print("1. ToolCallWidget test passed!")

# 2. Test DocumentDialog add menu
dialog = DocumentDialog()
menu = dialog._create_add_menu()
actions = [a.text() for a in menu.actions()]
print("Top-level menu actions:", actions)
assert "Ajouter un PDF ou une image" in actions

# Verify submenus exist
submenus = [a.menu() for a in menu.actions() if a.menu() is not None]
assert len(submenus) > 0, "No submenus created for skills!"
submenu_titles = [m.title() for m in submenus]
print("Discovered skill submenus:", submenu_titles)

# 3. Test selection of an action
dialog._on_skill_tool_selected("pdf", "create_pdf")
assert "Créer un document PDF" in dialog.question.toPlainText()
assert dialog._pending_forced_tool == "create_pdf"
print("2. Question text prefilled:", dialog.question.toPlainText())

# 4. Test tool event recording in a turn
dialog.begin_response("Ma demande de test")
dialog.record_tool_event("appel", "create_pdf", tool_data['arguments'])
turn = dialog.turns[dialog.current_turn_index]
assert len(turn['tools']) == 1
assert turn['tools'][0]['status'] == "running"
print("3. Tool call recorded in turn successfully!")

dialog.record_tool_event("résultat", "create_pdf", '{"success": true, "path": "output/test.pdf"}')
assert turn['tools'][0]['status'] == "done"
assert "test.pdf" in turn['tools'][0]['result']
print("4. Tool result recorded in turn successfully!")

# 5. Test append_response
dialog.append_response("Document créé avec succès.")
dialog.finish_response()
assert turn['tools'][0]['status'] == "done"
print("5. Conversation finish response passed!")

print("ALL TESTS PASSED SUCCESSFULLY!")
