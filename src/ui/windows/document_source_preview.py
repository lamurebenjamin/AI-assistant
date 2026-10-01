"""Affichage agrandi d'une capture de source documentaire."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout
from qfluentwidgets import SmoothScrollArea

from src.ui.stylesheet import qss_document_preview_dialog


def _show_source_image_large(self, image_path, source_title="Source surlignée"):
    """Affiche la capture à un tiers de la taille x2 précédente."""
    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        return
    # La fenêtre précédente affichait 2 fois la taille de la capture.
    # On divise cette taille par 3, soit 2/3 de la capture originale.
    target_width = max(1, round(pixmap.width() * 2 / 3))
    target_height = max(1, round(pixmap.height() * 2 / 3))
    zoomed = pixmap.scaled(
        target_width,
        target_height,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )
    dialog = QDialog(self)
    dialog.setWindowTitle(source_title)
    dialog.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
    dialog.setStyleSheet(qss_document_preview_dialog())
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    scroll = SmoothScrollArea(dialog)
    scroll.setWidgetResizable(False)
    scroll.setAlignment(Qt.AlignCenter)
    label = QLabel()
    label.setPixmap(zoomed)
    label.setFixedSize(zoomed.size())
    scroll.setWidget(label)
    layout.addWidget(scroll)

    # La fenêtre épouse l'image zoomée. Si elle dépasse l'écran, elle est
    # limitée à la zone disponible et les barres de défilement prennent le relais.
    screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
    available = screen.availableGeometry()
    frame_extra_width = 24
    frame_extra_height = 54
    target_width = zoomed.width() + 20 + frame_extra_width
    target_height = zoomed.height() + 20 + frame_extra_height
    dialog.resize(
        min(target_width, available.width() - 30),
        min(target_height, available.height() - 30),
    )
    dialog.exec()
