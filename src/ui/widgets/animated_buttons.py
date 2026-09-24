"""Boutons animés partagés par les fenêtres de l'application.

Source unique d'icônes
----------------------
Toutes les icônes proviennent du registre ``src.ui.icons.ICONS_DARK`` (défini
dans ``_SVG`` de icons.py). Pour ajouter ou modifier une icône :
  1. Ajouter/modifier le chemin SVG dans ``_SVG`` (icons.py).
  2. Ajuster ``_DARK_STROKE`` si l'épaisseur doit différer du défaut.
  3. Relancer ``tests/test_icon_consistency.py`` pour valider.

AnimatedComposerButton (Ctrl+9 / barre de composition)
  - Icônes rendues au format ICON_SIZE_COMPOSER (14 px).
  - Animations par kind : rotation du + (add), saut vertical (mic).

AnimatedHeaderButton (Ctrl+7 / fenêtre principale)
  - Icône fournie à la construction depuis ICONS_DARK.
  - Animation audio oscillante pour le bouton de lecture (is_audio=True).
"""

import math
import random

import numpy as np
from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QPushButton
from qfluentwidgets import ToolTipFilter as _ToolTipFilter

import src.ui.design_tokens as t

# ─── Helpers partagés ────────────────────────────────────────────────────────

def _hover_overlay(pressed: bool) -> QColor:
    alpha = 36 if pressed else 20
    if t.is_dark_theme():
        return QColor(255, 255, 255, alpha)
    return QColor(0, 0, 0, alpha)


def _install_tooltip_filter(widget: QPushButton, text: str) -> None:
    """Assigne le tooltip et installe ToolTipFilter une seule fois."""
    widget.setToolTip.__func__(widget, text)  # appel base Qt sans récursion
    if text:
        for f in widget.children():
            if isinstance(f, _ToolTipFilter):
                return
        widget.installEventFilter(_ToolTipFilter(widget, showDelay=300))


# ─── AnimatedComposerButton ───────────────────────────────────────────────────

class AnimatedComposerButton(QPushButton):
    """Bouton carré : cercle de survol Fluent + icône centrée depuis ICONS_DARK.

    Toutes les icônes proviennent du registre central ``src.ui.icons.ICONS_DARK``
    (défini dans ``_SVG`` de icons.py). Pour changer une icône, modifier ``_SVG``.
    Les animations spécifiques par kind (rotation du +, saut du micro) sont
    appliquées via des transforms QPainter avant le rendu de l'icône.
    """

    BUTTON_SIZE    = QSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
    HOVER_DIAMETER = float(t.BUTTON_HOVER_DIAMETER)
    # Taille rendue de l'icône — doit correspondre à ICON_SIZE_CLOSE du header
    # pour que le bouton Fermer soit identique dans Ctrl+7 et Ctrl+9.
    ICON_SIZE      = t.ICON_SIZE_COMPOSER

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
        # Initialisation sans déclencher setToolTip override (tooltip vide = pas de filtre)
        QPushButton.setToolTip(self, "")
        self.setIcon(QIcon())
        self.setStyleSheet("background:transparent;border:none;padding:0;margin:0;")

    # ── Property d'animation ──────────────────────────────────────────────────

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
            return  # pas d'animation pour le bouton fermer
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(float(target))
        self._animation.start()

    # ── Événements ───────────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self._animate_to(1.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_to(0.0)
        self.update()
        super().leaveEvent(event)

    def setToolTip(self, text: str) -> None:  # type: ignore[override]
        """Source unique pour les tooltips : installe ToolTipFilter automatiquement."""
        super().setToolTip(text)
        if text:
            for f in self.children():
                if isinstance(f, _ToolTipFilter):
                    return
            self.installEventFilter(_ToolTipFilter(self, showDelay=300))

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        from src.ui.icons import (
            ICONS_DARK,  # import tardif → évite les imports circulaires
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        # Cercle de survol
        if self.isEnabled() and (self.underMouse() or self.isDown()):
            d = self.HOVER_DIAMETER
            circle = QRectF(center.x() - d / 2.0, center.y() - d / 2.0, d, d)
            painter.setPen(Qt.NoPen)
            painter.setBrush(_hover_overlay(self.isDown()))
            painter.drawEllipse(circle)

        # Icône depuis ICONS_DARK (source unique — même registre que AnimatedHeaderButton)
        icon = ICONS_DARK.get(self.kind, QIcon())
        if icon.isNull():
            painter.end()
            return

        sz = self.ICON_SIZE
        icon_rect = QRectF(
            center.x() - sz / 2.0,
            center.y() - sz / 2.0,
            float(sz), float(sz),
        ).toRect()

        # Transforms d'animation par kind
        if self.kind == "add":
            # Rotation 0→-90° au survol pour indiquer l'ouverture du menu
            painter.save()
            painter.translate(center)
            painter.rotate(-90.0 * self._progress)
            painter.translate(-center.x(), -center.y())
            icon.paint(painter, icon_rect, Qt.AlignCenter)
            painter.restore()

        elif self.kind == "mic":
            # Saut vertical au survol + overlay de remplissage de la capsule
            jump = -2.5 * abs(np.sin(self._progress * np.pi))
            painter.save()
            painter.translate(QPointF(0.0, jump))
            icon.paint(painter, icon_rect, Qt.AlignCenter)
            if self._progress > 0.001:
                color = self.icon_color
                fill = QColor(color)
                fill.setAlphaF(0.45 * self._progress)
                painter.setPen(Qt.NoPen)
                painter.setBrush(fill)
                cap = QPainterPath()
                cx = float(icon_rect.center().x())
                cy = float(icon_rect.center().y()) - sz * 0.10
                cw, ch = sz * 0.25, sz * 0.42 * self._progress
                cap.addRoundedRect(
                    QRectF(cx - cw / 2.0, cy - ch / 2.0, cw, ch),
                    cw / 2.0, cw / 2.0,
                )
                painter.setClipPath(cap)
                painter.drawPath(cap)
                painter.setClipping(False)
            painter.restore()

        else:
            # close, send, stop : rendu direct sans transform
            icon.paint(painter, icon_rect, Qt.AlignCenter)

        painter.end()


# ─── AnimatedHeaderButton ─────────────────────────────────────────────────────

class AnimatedHeaderButton(QPushButton):
    """Bouton d'en-tête circulaire moderne avec animation fluide de survol et remplissage audio."""

    BUTTON_SIZE    = QSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
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
        self.setFocusPolicy(Qt.StrongFocus)
        self._icon = icon if icon is not None else QIcon()
        if tooltip:
            self.setToolTip(tooltip)
        self.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")

    # ── Animation audio ───────────────────────────────────────────────────────

    def _step_audio_animation(self) -> None:
        """Anime le niveau de remplissage de gauche à droite de manière fluide et aléatoire."""
        if self._is_hovered:
            self._phase += 0.14
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

    # ── Icon ──────────────────────────────────────────────────────────────────

    def setIcon(self, icon: QIcon) -> None:
        self._icon = icon
        self.update()

    def icon(self) -> QIcon:
        return self._icon

    # ── Property d'animation ──────────────────────────────────────────────────

    def get_animation_progress(self) -> float:
        return self._progress

    def set_animation_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    animationProgress = Property(
        float, fget=get_animation_progress, fset=set_animation_progress
    )

    # ── Événements ────────────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(1.0)
        self._animation.start()
        if self.is_audio and not self._audio_timer.isActive():
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

    def setToolTip(self, text: str) -> None:  # type: ignore[override]
        """Source unique pour les tooltips : installe ToolTipFilter automatiquement."""
        super().setToolTip(text)
        if text:
            for f in self.children():
                if isinstance(f, _ToolTipFilter):
                    return
            self.installEventFilter(_ToolTipFilter(self, showDelay=300))

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        d = self.HOVER_DIAMETER
        circle = QRectF(center.x() - d / 2.0, center.y() - d / 2.0, d, d)

        # Fond et remplissage animé
        if self.is_audio and (self._audio_fill > 0.001 or self._progress > 0.001 or self.isDown()):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 16 if not self.isDown() else 35))
            painter.drawEllipse(circle)

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

                painter.setPen(QPen(QColor(0, 0, 0, 60), 1.2, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(
                    QPointF(circle.x() + fill_w, circle.top() + 3),
                    QPointF(circle.x() + fill_w, circle.bottom() - 3),
                )
                painter.restore()
        elif self.isEnabled() and (self._progress > 0.001 or self.isDown()):
            overlay = _hover_overlay(self.isDown())
            if not self.isDown():
                overlay.setAlpha(max(1, int(overlay.alpha() * self._progress)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(overlay)
            painter.drawEllipse(circle)

        # Icône centrée
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

            # Remplissage synchronisé de l'icône audio de gauche à droite
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
