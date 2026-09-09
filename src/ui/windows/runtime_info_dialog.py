"""Boîte de dialogue affichant les informations d'exécution (CPU, GPU, RAM, VRAM, Modèle, Threads)."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout

from src.ui.design_tokens import (
    COLOR_BG_PAGE,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    FONT_TEXT,
    RADIUS_MD,
    SIZE_LG,
)


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
        light_palette = self.palette()
        light_palette.setColor(QPalette.Window, QColor(COLOR_BG_PAGE))
        light_palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT_PRIMARY))
        light_palette.setColor(QPalette.Base, QColor(COLOR_BG_SURFACE))
        light_palette.setColor(QPalette.Text, QColor(COLOR_TEXT_PRIMARY))
        self.setPalette(light_palette)
        self.setStyleSheet(
            f"QDialog {{ background:{COLOR_BG_PAGE}; }}"
            f"QLabel#RuntimeValues {{ color:{COLOR_TEXT_PRIMARY}; "
            f"font-family:{FONT_TEXT}; font-size:{SIZE_LG}; "
            f"background:{COLOR_BG_SURFACE}; border:1px solid {COLOR_BORDER}; border-radius:{RADIUS_MD}; "
            f"padding:14px; }}"
        )
        self.runtime_layout = QVBoxLayout(self)
        self.runtime_layout.setContentsMargins(18, 16, 18, 16)

        self.values_label = QLabel("Collecte des informations...")
        self.values_label.setObjectName("RuntimeValues")
        self.values_label.setWordWrap(True)
        self.values_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.runtime_layout.addWidget(self.values_label)
        self._adjust_height_to_content()

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
