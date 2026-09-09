"""Indicateur animé de réflexion (dots ondulants) avant le premier token généré."""

import math
from PyQt5.QtCore import QPointF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QWidget


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
            color = QColor("#397D58")
            color.setAlpha(int(115 + 105 * wave))
            painter.setBrush(color)
            x = 10.0 + index * 10.0
            painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.end()
