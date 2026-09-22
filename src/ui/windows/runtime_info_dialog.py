"""Boîte de dialogue affichant les informations d'exécution (CPU, GPU, RAM, VRAM, Modèle, Threads)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

import src.ui.design_tokens as t
from src.ui.stylesheet import qss_runtime_values


class RuntimeInfoDialog(QDialog):
    """Fenêtre compacte affichant les ressources de l'application."""

    WINDOW_WIDTH = 520
    MINIMUM_HEIGHT = 110
    MAXIMUM_HEIGHT = 220

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assistant IA")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setFixedWidth(self.WINDOW_WIDTH)
        self.setAutoFillBackground(True)
        self.runtime_layout = QVBoxLayout(self)
        self.runtime_layout.setContentsMargins(18, 16, 18, 16)

        self.values_label = QLabel("Collecte des informations...")
        self.values_label.setObjectName("RuntimeValues")
        self.values_label.setWordWrap(True)
        self.values_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.runtime_layout.addWidget(self.values_label)
        self.refresh_theme()
        self._adjust_height_to_content()

    def refresh_theme(self) -> None:
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(t.COLOR_BG_PAGE))
        palette.setColor(QPalette.WindowText, QColor(t.COLOR_TEXT_PRIMARY))
        palette.setColor(QPalette.Base, QColor(t.COLOR_BG_SURFACE))
        palette.setColor(QPalette.Text, QColor(t.COLOR_TEXT_PRIMARY))
        self.setPalette(palette)
        self.setStyleSheet(qss_runtime_values())

    def _adjust_height_to_content(self):
        """Adapte la hauteur au contenu tout en conservant un format compact."""
        self.runtime_layout.activate()
        content_height = self.runtime_layout.sizeHint().height()
        target_height = max(
            self.MINIMUM_HEIGHT,
            min(content_height, self.MAXIMUM_HEIGHT),
        )
        self.setFixedHeight(target_height)

    def set_information(self, information: str):
        self.values_label.setText(information)
        self.values_label.adjustSize()
        self._adjust_height_to_content()
