"""Indicateur animé de réflexion (dots ondulants) avant le premier token généré."""

import math
from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QWidget

import src.ui.design_tokens as t


class ThinkingDots(QWidget):
    """Trois petits points animés de façon continue avant le premier token."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self.animation_time = 0.0
        self.timer = QTimer(self)
        # Environ 33 images par seconde pour un mouvement fluide sans charger Qt.
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._advance)
        self.timer.start()

    def _advance(self):
        self.animation_time = (self.animation_time + 0.19) % (2.0 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        center_y = self.height() / 2.0
        for index in range(3):
            # Onde sinusoïdale décalée, avec déplacement vertical et variation
            # très légère de taille et d'opacité.
            wave = (math.sin(self.animation_time - index * 0.85) + 1.0) / 2.0
            radius = 1.55 + 0.45 * wave
            y = center_y - 1.8 * wave
            color = QColor(t.COLOR_SUCCESS)
            color.setAlpha(int(115 + 105 * wave))
            painter.setBrush(color)
            x = 10.0 + index * 10.0
            painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.end()


class GenerationSpinner(QWidget):
    """Anneau bleu rotatif affiché pendant la génération de la réponse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(24)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _advance(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        pen = QPen(QColor(t.COLOR_PRIMARY))
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(-8, -8, 16, 16, 45 * 16, 270 * 16)
        painter.end()


class ShimmerLabel(QWidget):
    """Texte de statut affiché dans une couleur uniforme."""

    def __init__(self, text="", parent=None, italic=True):
        super().__init__(parent)
        self.text = text
        self._italic = italic
        self._text_color = QColor(t.COLOR_TEXT_SECONDARY)
        self._offset = -1.0
        self.setMinimumHeight(22)
        self.setMinimumWidth(170)
        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._advance)

    def stop_animation(self):
        self._timer.stop()
        self.update()

    def start_animation(self):
        if not self._timer.isActive():
            self._timer.start()

    def _advance(self):
        self._offset += 0.04
        if self._offset > 1.25:
            self._offset = -0.25
        self.update()

    def set_status_text(self, text):
        self.text = text or ""
        self.updateGeometry()
        self.update()

    def set_text_color(self, color):
        self._text_color = QColor(color)
        self.update()

    def sizeHint(self):
        font = QFont(self.font())
        font.setItalic(self._italic)
        metrics = QFontMetrics(font)
        return QSize(
            metrics.horizontalAdvance(self.text) + 2,
            max(t.HEADER_ROW_HEIGHT, metrics.height() + 2),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        font = QFont(self.font())
        font.setItalic(self._italic)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        baseline = (
            (self.height() - metrics.height()) // 2
            + metrics.ascent()
        )
        if self._timer.isActive():
            gradient = QLinearGradient(0, 0, max(1, self.width()), 0)
            center = max(0.0, min(1.0, self._offset))
            base_color = QColor(self._text_color)
            highlight_color = QColor(t.COLOR_TEXT_ACTIVE)
            gradient.setColorAt(0.0, base_color)
            gradient.setColorAt(max(0.0, center - 0.12), base_color)
            gradient.setColorAt(center, highlight_color)
            gradient.setColorAt(min(1.0, center + 0.12), base_color)
            gradient.setColorAt(1.0, base_color)
            painter.setPen(QPen(gradient, 1))
        else:
            painter.setPen(QPen(self._text_color, 1))
        painter.drawText(0, baseline, self.text)
        painter.end()
