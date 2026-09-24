"""Menu et dialogue documentaire de l'AssistantWindow.

Le but de ce module est d'isoler les responsabilités liées à la navigation,
à l'ouverture du menu contextuel et à la gestion de la fenêtre Ctrl+9 afin de
réduire la taille de l'orchestre principal.
"""

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Action as FluentAction
from qfluentwidgets import RoundMenu


class AssistantWindowMenuController:
    """Construit et affiche le menu contextuel de l'assistant."""

    def __init__(self, host):
        self.host = host

    def show_menu(self):
        host = self.host
        host.selected_text = host.get_selected_text()
        host.update_window_title()

        menu = RoundMenu(parent=None)
        for index, action in enumerate(host.config['actions']):
            display_name = action['name']
            if index < 9:
                display_name = f"{index + 1}  \u2022  {display_name}"
            menu_action = FluentAction(display_name)
            menu_action.triggered.connect(lambda checked=False, action_cfg=action: host.execute_action(action_cfg))
            menu.addAction(menu_action)

        menu.addSeparator()
        document_action = FluentAction("9  \u2022  Interroger mes documents")
        document_action.triggered.connect(host.show_document_dialog)
        menu.addAction(document_action)

        menu.addSeparator()
        action_param = FluentAction("Paramètres")
        action_param.triggered.connect(host.open_settings)
        menu.addAction(action_param)

        action_quit = FluentAction("Quitter")
        action_quit.triggered.connect(host.quit_application)
        menu.addAction(action_quit)

        menu.exec(QCursor.pos())


class AssistantWindowDocumentController:
    """Gère la fenêtre de dialogue documentaire et son emplacement."""

    def __init__(self, host):
        self.host = host

    def toggle_window(self):
        host = self.host
        if host.document_dialog is not None:
            if host.document_dialog.isVisible():
                host.document_dialog.hide()
            else:
                host.document_dialog.show()
                host.document_dialog.raise_()
                host.document_dialog.activateWindow()
                for delay in (0, 80, 180):
                    host.document_dialog.focus_message_input()
            return

        if not host.isVisible():
            return
        if host.is_collapsed:
            host.expanded_height = host.calculate_expanded_height()
            host.animate_height(host.expanded_height, True)
        else:
            host.animate_height(38, False)

    def show_dialog(self):
        host = self.host
        if host.document_dialog is not None and host.document_dialog.isVisible():
            host.document_dialog.raise_()
            host.document_dialog.activateWindow()
            for delay in (0, 80, 180):
                host.document_dialog.focus_message_input()
            return

        host.document_history = []
        host.document_session_documents = []
        from src.ui.windows.document_dialog import DocumentDialog

        host.document_dialog = DocumentDialog(host)
        self._restore_position(host.document_dialog)
        host.document_dialog.ask_requested.connect(host.start_document_analysis)
        host.document_dialog.finished.connect(host._remember_document_dialog_position)
        host.document_dialog.show()
        host.document_dialog.raise_()
        host.document_dialog.activateWindow()
        for delay in (0, 80, 180):
            host.document_dialog.focus_message_input()

    def remember_position(self, _result=0):
        host = self.host
        dialog = host.document_dialog
        if dialog is not None:
            host.document_dialog_position = QPoint(dialog.pos())
            host.document_dialog = None

    def _restore_position(self, dialog):
        host = self.host
        position = host.document_dialog_position
        if position is None:
            parent_rect = host.frameGeometry()
            position = parent_rect.topLeft() + QPoint(24, 24)

        screen = QApplication.screenAt(position) or QApplication.primaryScreen()
        if screen is None:
            dialog.move(position)
            return
        available = screen.availableGeometry()
        x = max(
            available.left(),
            min(position.x(), available.right() - dialog.width() + 1),
        )
        y = max(
            available.top(),
            min(position.y(), available.bottom() - dialog.height() + 1),
        )
        dialog.move(x, y)
