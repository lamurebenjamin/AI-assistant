"""Boutons interactifs avec animations vectorielles fluides."""

import numpy as np
from PyQt5.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
)
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QPushButton

from src.ui.design_tokens import COLOR_TEXT_PRIMARY


class AnimatedComposerButton(QPushButton):
    """Bouton carré avec cercle de survol et icône centrés exactement."""

    # Même couleur et même épaisseur de trait que l'icône de fermeture "x".
    ICON_COLOR = QColor(COLOR_TEXT_PRIMARY)
    ICON_STROKE_WIDTH = 1.2
    BUTTON_SIZE = QSize(28, 28)
    HOVER_DIAMETER = 26.0
    ICON_EXTENT = 6.5

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._progress = 0.0
        self._animation = QPropertyAnimation(self, b"animationProgress", self)
        self._animation.setDuration(220 if kind == "mic" else 190)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setFixedSize(self.BUTTON_SIZE)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("")
        self.setIcon(QIcon())
        self.setStyleSheet("background:transparent;border:none;padding:0;margin:0;")

    def get_animation_progress(self) -> float:
        return self._progress

    def set_animation_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    animationProgress = pyqtProperty(
        float, fget=get_animation_progress, fset=set_animation_progress
    )

    def _animate_to(self, target: float) -> None:
        if self.kind == "close":
            return
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(float(target))
        self._animation.start()

    def enterEvent(self, event) -> None:
        self._animate_to(1.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_to(0.0)
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        if self.underMouse() or self.isDown():
            d = self.HOVER_DIAMETER
            circle = QRectF(center.x() - d / 2.0, center.y() - d / 2.0, d, d)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 28 if self.isDown() else 18))
            painter.drawEllipse(circle)

        pen = QPen(self.ICON_COLOR)
        pen.setWidthF(self.ICON_STROKE_WIDTH)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if self.kind == "add":
            painter.save()
            painter.translate(center)
            painter.rotate(-90.0 * self._progress)
            a = self.ICON_EXTENT
            painter.drawLine(QPointF(-a, 0.0), QPointF(a, 0.0))
            painter.drawLine(QPointF(0.0, -a), QPointF(0.0, a))
            painter.restore()

        elif self.kind == "stop":
            painter.save()
            painter.translate(center)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.ICON_COLOR)
            painter.drawRoundedRect(QRectF(-5, -5, 10, 10), 2, 2)
            painter.restore()

        elif self.kind == "send":
            painter.save()
            painter.translate(center)
            a = self.ICON_EXTENT
            path = QPainterPath()
            path.moveTo(-a, -a * 0.72)
            path.lineTo(a, 0.0)
            path.lineTo(-a, a * 0.72)
            path.lineTo(-a * 0.34, 0.0)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(QPointF(-a * 0.34, 0.0), QPointF(a, 0.0))
            painter.restore()

        elif self.kind == "mic":
            painter.save()
            jump = -2.5 * abs(np.sin(self._progress * np.pi))
            painter.translate(center.x(), center.y() + jump)
            capsule = QPainterPath()
            capsule.addRoundedRect(QRectF(-2.4, -6.5, 4.8, 8.0), 2.4, 2.4)
            painter.drawPath(capsule)
            painter.drawArc(QRectF(-5.0, -2.5, 10.0, 7.0), 180 * 16, 180 * 16)
            painter.drawLine(QPointF(0.0, 4.5), QPointF(0.0, 6.5))
            painter.drawLine(QPointF(-3.2, 6.5), QPointF(3.2, 6.5))
            if self._progress > 0.001:
                painter.save()
                painter.setClipPath(capsule)
                h = 8.0 * self._progress
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.ICON_COLOR)
                painter.drawRect(QRectF(-2.4, 1.5 - h, 4.8, h))
                painter.restore()
            painter.restore()

        else:  # close
            painter.save()
            painter.translate(center)
            a = self.ICON_EXTENT
            painter.drawLine(QPointF(-a, -a), QPointF(a, a))
            painter.drawLine(QPointF(a, -a), QPointF(-a, a))
            painter.restore()

        painter.end()


class AnimatedHeaderButton(QPushButton):
    """Bouton d'en-tête circulaire moderne avec animation fluide de survol."""

    BUTTON_SIZE = QSize(28, 28)
    HOVER_DIAMETER = 26.0

    def __init__(self, icon: QIcon = None, tooltip: str = "", parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._animation = QPropertyAnimation(self, b"animationProgress", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setFixedSize(self.BUTTON_SIZE)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._icon = icon if icon is not None else QIcon()
        if tooltip:
            self.setToolTip(tooltip)
        self.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")

    def setIcon(self, icon: QIcon) -> None:
        self._icon = icon
        self.update()

    def icon(self) -> QIcon:
        return self._icon

    def get_animation_progress(self) -> float:
        return self._progress

    def set_animation_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    animationProgress = pyqtProperty(
        float, fget=get_animation_progress, fset=set_animation_progress
    )

    def enterEvent(self, event) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(1.0)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(0.0)
        self._animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        # Rond de survol animé avec opacité progressive
        if self._progress > 0.001 or self.isDown():
            d = self.HOVER_DIAMETER
            circle = QRectF(center.x() - d / 2.0, center.y() - d / 2.0, d, d)
            alpha = 35 if self.isDown() else int(22 * self._progress)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawEllipse(circle)

        # Dessin de l'icône centrée
        if not self._icon.isNull():
            icon_sz = self.iconSize()
            if icon_sz.isEmpty():
                icon_sz = QSize(18, 18)
            rect = QRectF(
                center.x() - icon_sz.width() / 2.0,
                center.y() - icon_sz.height() / 2.0,
                icon_sz.width(),
                icon_sz.height(),
            )
            self._icon.paint(painter, rect.toRect(), Qt.AlignCenter)

        painter.end()

