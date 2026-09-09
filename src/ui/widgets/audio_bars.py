"""Indicateurs audio animés pour la captation microphone."""

import numpy as np
from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QWidget

from src.ui.design_tokens import COLOR_AUDIO_ACTIVE, COLOR_AUDIO_IDLE


class LiveAudioIndicator(QWidget):
    """Animation moderne et réactive au niveau sonore du microphone."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(106, 24)
        self._level = 0.0
        self._display_level = 0.0
        self._phase = 0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._animate)

    def start(self):
        self._active = True
        self._timer.start()
        self.update()

    def stop(self):
        self._active = False
        self._level = 0.0
        self._timer.stop()
        self.update()

    def set_level(self, value):
        self._level = max(0.0, min(1.0, float(value) / 100.0))
        if self._active and not self._timer.isActive():
            self._timer.start()

    def _animate(self):
        # Lissage rapide à la montée, plus doux à la descente.
        factor = 0.55 if self._level > self._display_level else 0.18
        self._display_level += (self._level - self._display_level) * factor
        self._phase = (self._phase + 1) % 1000
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        bar_count = 13
        bar_width = 4
        gap = 4
        total_width = bar_count * bar_width + (bar_count - 1) * gap
        x0 = (self.width() - total_width) / 2.0
        center_y = self.height() / 2.0
        audible = self._display_level > 0.025
        base_color = QColor(COLOR_AUDIO_ACTIVE if audible else COLOR_AUDIO_IDLE)
        for index in range(bar_count):
            distance = abs(index - (bar_count - 1) / 2.0)
            shape = max(0.25, 1.0 - distance / 8.0)
            pulse = 0.76 + 0.24 * abs(np.sin((self._phase + index * 8) * 0.09))
            height = 4.0 + (self.height() - 6.0) * self._display_level * shape * pulse
            height = max(4.0, min(self.height() - 2.0, height))
            color = QColor(base_color)
            color.setAlpha(235 if audible else 135)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(
                QRectF(
                    x0 + index * (bar_width + gap),
                    center_y - height / 2.0,
                    bar_width,
                    height,
                ),
                2.0,
                2.0,
            )
        painter.end()


class ScrollingAudioBars(QWidget):
    """Barres audio défilantes horizontales pour le retour sonore."""

    BAR_WIDTH = 3.0
    BAR_GAP = 3.0
    MIN_HEIGHT = 3.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setMinimumWidth(40)
        self.setSizePolicy(self.sizePolicy().Expanding, self.sizePolicy().Fixed)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._target_level = 0.0
        self._display_level = 0.0
        self._levels = []
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._advance)
        self.hide()

    def start(self):
        self._levels.clear()
        self._target_level = 0.0
        self._display_level = 0.0
        self._active = True
        self.show()
        self._timer.start()
        self.update()

    def stop(self):
        self._active = False
        self._timer.stop()
        self._levels.clear()
        self.hide()
        self.update()

    def set_level(self, value):
        self._target_level = max(0.0, min(1.0, float(value) / 100.0))

    def _capacity(self):
        return max(
            1,
            int((max(1, self.width()) + self.BAR_GAP) / (self.BAR_WIDTH + self.BAR_GAP)),
        )

    def _advance(self):
        if not self._active:
            return
        factor = 0.62 if self._target_level > self._display_level else 0.24
        self._display_level += (self._target_level - self._display_level) * factor
        self._levels.append(self._display_level)
        if len(self._levels) > self._capacity():
            del self._levels[:-self._capacity()]
        self.update()

    def paintEvent(self, event):
        if not self._active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        center = self.height() / 2.0
        step = self.BAR_WIDTH + self.BAR_GAP
        right = self.width() - self.BAR_WIDTH
        count = len(self._levels)
        for i, level in enumerate(self._levels):
            x = right - (count - 1 - i) * step
            if x + self.BAR_WIDTH < 0:
                continue
            if level <= 0.025:
                height = self.BAR_WIDTH
            else:
                amplified = min(1.0, level * 1.18)
                height = self.MIN_HEIGHT + amplified * (
                    self.height() - self.MIN_HEIGHT - 1.0
                )
            color = QColor(82, 91, 102, 105 + int(105 * min(1.0, level * 1.8)))
            painter.setBrush(color)
            painter.drawRoundedRect(
                QRectF(x, center - height / 2.0, self.BAR_WIDTH, height),
                self.BAR_WIDTH / 2.0,
                self.BAR_WIDTH / 2.0,
            )
        painter.end()
