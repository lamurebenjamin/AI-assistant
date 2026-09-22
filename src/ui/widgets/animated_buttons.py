import math
import random
import numpy as np
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Property,
)
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton, QToolTip

import src.ui.design_tokens as t


def _hover_overlay(pressed: bool) -> QColor:
    alpha = 36 if pressed else 20
    if t.is_dark_theme():
        return QColor(255, 255, 255, alpha)
    return QColor(0, 0, 0, alpha)


def _draw_focus_ring(painter: QPainter, center: QPointF, diameter: float) -> None:
    """Anneau de focus visible dans les deux thèmes, indépendant du survol."""
    pen = QPen(QColor(t.COLOR_PRIMARY))
    pen.setWidthF(1.6)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(
        QRectF(
            center.x() - diameter / 2.0,
            center.y() - diameter / 2.0,
            diameter,
            diameter,
        )
    )


class AnimatedComposerButton(QPushButton):
    """Bouton carré avec cercle de survol et icône centrés exactement."""

    # Même couleur et même épaisseur de trait que l'icône de fermeture "x".
    ICON_STROKE_WIDTH = t.ICON_STROKE_WIDTH
    BUTTON_SIZE = QSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
    HOVER_DIAMETER = float(t.BUTTON_HOVER_DIAMETER)
    ICON_EXTENT = 6.5

    @property
    def icon_color(self) -> QColor:
        if not self.isEnabled():
            return QColor(t.COLOR_TEXT_MUTED)
        return QColor(t.COLOR_TEXT_PRIMARY)

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
        self.setFocusPolicy(Qt.StrongFocus)
        self.setToolTip("")
        self.setIcon(QIcon())
        self.setStyleSheet("background:transparent;border:none;padding:0;margin:0;")

    def get_animation_progress(self) -> float:
        return self._progress

    def set_animation_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    animationProgress = Property(
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

    def event(self, event) -> bool:
        if event.type() == QEvent.ToolTip:
            tip = self.toolTip()
            if tip:
                QToolTip.showText(event.globalPos(), tip, None)
                return True
        return super().event(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        if self.isEnabled() and (self.underMouse() or self.isDown() or self.hasFocus()):
            d = self.HOVER_DIAMETER
            circle = QRectF(center.x() - d / 2.0, center.y() - d / 2.0, d, d)
            painter.setPen(Qt.NoPen)
            painter.setBrush(_hover_overlay(self.isDown()))
            painter.drawEllipse(circle)
        if self.hasFocus() and self.isEnabled():
            _draw_focus_ring(painter, center, self.HOVER_DIAMETER)

        color = self.icon_color
        pen = QPen(color)
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
            painter.setBrush(color)
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
                painter.setBrush(color)
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
    """Bouton d'en-tête circulaire moderne avec animation fluide de survol et remplissage audio."""

    BUTTON_SIZE = QSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
    HOVER_DIAMETER = float(t.BUTTON_HOVER_DIAMETER)

    def __init__(
        self,
        icon: QIcon = None,
        tooltip: str = "",
        parent=None,
        is_audio: bool = False,
    ):
        super().__init__(parent)
        self.is_audio = is_audio
        self._progress = 0.0
        self._audio_fill = 0.0
        self._audio_target = 0.0
        self._phase = 0.0
        self._is_hovered = False
        self._icon_filled = None
        self._animation = QPropertyAnimation(self, b"animationProgress", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

        if self.is_audio:
            self._audio_timer = QTimer(self)
            self._audio_timer.setInterval(30)
            self._audio_timer.timeout.connect(self._step_audio_animation)

        self.setFixedSize(self.BUTTON_SIZE)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        # Navigable au clavier : le focus dessine un anneau primaire dans paintEvent.
        self.setFocusPolicy(Qt.StrongFocus)
        self._icon = icon if icon is not None else QIcon()
        if tooltip:
            self.setToolTip(tooltip)
        self.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")

    def _step_audio_animation(self) -> None:
        """Anime le niveau de remplissage de gauche à droite de manière fluide et aléatoire."""
        if self._is_hovered:
            self._phase += 0.14
            # Somme d'harmoniques et léger jitter pour un mouvement vivant de signal audio
            base = 0.60 + 0.26 * math.sin(self._phase * 1.7) + 0.12 * math.sin(self._phase * 3.4 + 0.6)
            jitter = (random.random() - 0.5) * 0.08
            self._audio_target = max(0.25, min(0.95, base + jitter))
            self._audio_fill += (self._audio_target - self._audio_fill) * 0.32
        else:
            self._audio_fill += (0.0 - self._audio_fill) * 0.28
            if self._audio_fill < 0.01:
                self._audio_fill = 0.0
                self._audio_timer.stop()
        self.update()

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

    animationProgress = Property(
        float, fget=get_animation_progress, fset=set_animation_progress
    )

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(1.0)
        self._animation.start()
        if self.is_audio:
            if not self._audio_timer.isActive():
                self._audio_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(0.0)
        self._animation.start()
        if self.is_audio:
            self._audio_target = 0.0
        super().leaveEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.ToolTip:
            tip = self.toolTip()
            if tip:
                QToolTip.showText(event.globalPos(), tip, None)
                return True
        return super().event(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        d = self.HOVER_DIAMETER
        circle = QRectF(center.x() - d / 2.0, center.y() - d / 2.0, d, d)

        # Fond et remplissage animé
        if self.is_audio and (self._audio_fill > 0.001 or self._progress > 0.001 or self.isDown()):
            # Fond circulaire léger de base
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 16 if not self.isDown() else 35))
            painter.drawEllipse(circle)

            # Remplissage de gauche à droite oscillant
            if self._audio_fill > 0.001:
                painter.save()
                clip_path = QPainterPath()
                clip_path.addEllipse(circle)
                painter.setClipPath(clip_path)

                fill_w = circle.width() * self._audio_fill
                fill_rect = QRectF(circle.x(), circle.y(), fill_w, circle.height())
                grad = QLinearGradient(circle.x(), 0, circle.right(), 0)
                grad.setColorAt(0.0, QColor(0, 0, 0, 22))
                grad.setColorAt(max(0.0, min(1.0, self._audio_fill)), QColor(0, 0, 0, 48))
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.NoPen)
                painter.drawRect(fill_rect)

                # Fin trait d'onde au front de remplissage
                painter.setPen(QPen(QColor(0, 0, 0, 60), 1.2, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(
                    QPointF(circle.x() + fill_w, circle.top() + 3),
                    QPointF(circle.x() + fill_w, circle.bottom() - 3),
                )
                painter.restore()
        elif self.isEnabled() and (self._progress > 0.001 or self.isDown() or self.hasFocus()):
            overlay = _hover_overlay(self.isDown())
            if not self.isDown() and not self.hasFocus():
                overlay.setAlpha(max(1, int(overlay.alpha() * self._progress)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(overlay)
            painter.drawEllipse(circle)

        if self.hasFocus() and self.isEnabled():
            _draw_focus_ring(painter, center, d)

        # Dessin de l'icône centrée
        if not self._icon.isNull():
            icon_sz = self.iconSize()
            if icon_sz.isEmpty():
                icon_sz = QSize(t.ICON_SIZE_BUTTON, t.ICON_SIZE_BUTTON)
            rect = QRectF(
                center.x() - icon_sz.width() / 2.0,
                center.y() - icon_sz.height() / 2.0,
                icon_sz.width(),
                icon_sz.height(),
            )
            self._icon.paint(painter, rect.toRect(), Qt.AlignCenter)

            # Remplissage synchronisé de l'icône son de gauche à droite
            if self.is_audio and self._audio_fill > 0.001:
                if self._icon_filled is None:
                    from src.ui.icons import ICONS_DARK
                    self._icon_filled = ICONS_DARK.get("speak_filled")
                if self._icon_filled is not None and not self._icon_filled.isNull():
                    painter.save()
                    fill_w = circle.width() * self._audio_fill
                    painter.setClipRect(
                        QRectF(circle.x(), circle.y(), fill_w, circle.height())
                    )
                    self._icon_filled.paint(painter, rect.toRect(), Qt.AlignCenter)
                    painter.restore()

        painter.end()
