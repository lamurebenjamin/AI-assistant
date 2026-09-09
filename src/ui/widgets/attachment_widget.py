"""Widget de prévisualisation des fichiers et images joints."""

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class AttachmentPreviewWidget(QWidget):
    """Carte de pièce jointe avec contour arrondi et croix au survol."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.close_button = None
        self.setMouseTracking(True)

    def set_close_button(self, button):
        self.close_button = button
        button.hide()

    def enterEvent(self, event):
        if self.close_button is not None:
            self.close_button.show()
            self.close_button.raise_()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.close_button is not None:
            self.close_button.hide()
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(112, 120, 130, 145 if self.underMouse() else 105))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255, 24))
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0), 9.0, 9.0
        )
        painter.end()
