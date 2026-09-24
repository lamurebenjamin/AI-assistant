"""Reusable collapsible timeline header primitives."""

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

import src.ui.design_tokens as t
from src.ui.icons import create_svg_icon
from src.ui.stylesheet import qss_timeline_header_title, qss_transparent_surface

CHEVRON_SPACING = 4
CHEVRON_FONT_SIZE = 18
CHEVRON_WIDTH = 14


class ChevronLabel(QLabel):
    """Chevron unique dont l'état déplié est une rotation exacte de 90 degrés."""

    def __init__(self, parent=None):
        super().__init__("›", parent)
        self._expanded = False
        self._angle = 0.0
        self._color = t.COLOR_TEXT_PRIMARY
        self._rotation_animation = QPropertyAnimation(
            self, b"rotationAngle", self
        )
        self._rotation_animation.setDuration(190)
        self._rotation_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setFixedWidth(CHEVRON_WIDTH)
        self.setFixedHeight(t.HEADER_ROW_HEIGHT)
        self.setContentsMargins(0, 0, 0, 0)
        self.setAlignment(Qt.AlignCenter)

    def get_rotation_angle(self) -> float:
        return self._angle

    def set_rotation_angle(self, value: float) -> None:
        self._angle = max(0.0, min(90.0, float(value)))
        self.update()

    rotationAngle = Property(
        float, fget=get_rotation_angle, fset=set_rotation_angle
    )

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        self._expanded = bool(expanded)
        target_angle = 90.0 if self._expanded else 0.0
        self._rotation_animation.stop()
        if animate:
            self._rotation_animation.setStartValue(self._angle)
            self._rotation_animation.setEndValue(target_angle)
            self._rotation_animation.start()
        else:
            self.set_rotation_angle(target_angle)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self._color)
        font = QFont(self.font())
        font.setPixelSize(CHEVRON_FONT_SIZE)
        painter.setFont(font)
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.rotate(self._angle)
        painter.drawText(
            QRectF(
                -self.width() / 2.0,
                -self.height() / 2.0,
                self.width(),
                self.height(),
            ),
            Qt.AlignCenter,
            "›",
        )
        painter.end()


class CollapsibleHeader(QWidget):
    """En-tête partagé des blocs repliables de la timeline."""

    hovered = Signal(bool)

    def __init__(self, title_widget: QWidget, expanded: bool, parent=None, icon_svg=""):
        super().__init__(parent)
        self._expanded = expanded
        self._hovered = False
        self._animating = False
        self._animation_phase = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.installEventFilter(self)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self.setFixedHeight(t.HEADER_ROW_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(CHEVRON_SPACING)
        self.title_widget = title_widget
        self.icon_label = None
        self.icon_svg = icon_svg
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(28)
        self._animation_timer.timeout.connect(self._advance_animation)
        if icon_svg:
            self.icon_label = QLabel(self)
            self.icon_label.setPixmap(
                create_svg_icon(
                    icon_svg, t.COLOR_TEXT_SECONDARY, 1.5
                ).pixmap(t.ICON_SIZE_THINKING, t.ICON_SIZE_THINKING)
            )
            self.icon_label.setFixedSize(
                t.ICON_SIZE_THINKING, t.ICON_SIZE_THINKING
            )
            self.icon_label.setAlignment(Qt.AlignCenter)
            self.icon_label.setStyleSheet(qss_transparent_surface())
            layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(title_widget, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.chevron = ChevronLabel(self)
        layout.addWidget(self.chevron, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.set_expanded(expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.chevron.set_expanded(self._expanded)
        self.chevron.setVisible(self._expanded or self._hovered)
        self._update_title_color()

    def _update_title_color(self) -> None:
        self.set_title_color(
            t.COLOR_TEXT_SECONDARY
            if self._animating
            else t.COLOR_TEXT_ACTIVE
            if self._expanded or self._hovered
            else t.COLOR_TEXT_SECONDARY
        )

    def set_title(self, text: str) -> None:
        if hasattr(self.title_widget, "setText"):
            self.title_widget.setText(text)
        elif hasattr(self.title_widget, "set_status_text"):
            self.title_widget.set_status_text(text)

    def set_title_color(self, color: str) -> None:
        if self.icon_label is not None:
            self.icon_label.setPixmap(
                create_svg_icon(
                    self.icon_svg, color, 1.5
                ).pixmap(t.ICON_SIZE_THINKING, t.ICON_SIZE_THINKING)
            )
        if hasattr(self.title_widget, "set_text_color"):
            self.title_widget.set_text_color(color)
        else:
            self.title_widget.setStyleSheet(qss_timeline_header_title(color))

    def set_animation(self, active: bool) -> None:
        self._animating = bool(active)
        if hasattr(self.title_widget, "start_animation"):
            (self.title_widget.start_animation if active else self.title_widget.stop_animation)()
        if active:
            self._animation_timer.start()
        else:
            self._animation_timer.stop()
        self._update_title_color()

    def _advance_animation(self) -> None:
        self._animation_phase = (self._animation_phase + 0.04) % 1.4
        if self.icon_label is not None:
            wave = max(0.0, 1.0 - abs(self._animation_phase - 0.7) / 0.28)
            base = QColor(t.COLOR_TEXT_SECONDARY)
            active = QColor(t.COLOR_TEXT_ACTIVE)
            color = QColor(
                round(base.red() + (active.red() - base.red()) * wave),
                round(base.green() + (active.green() - base.green()) * wave),
                round(base.blue() + (active.blue() - base.blue()) * wave),
            )
            self.icon_label.setPixmap(
                create_svg_icon(
                    self.icon_svg, color.name(), 1.5
                ).pixmap(t.ICON_SIZE_THINKING, t.ICON_SIZE_THINKING)
            )

    def eventFilter(self, watched, event):
        if watched is self and event.type() == QEvent.Enter:
            self._hovered = True
            self._update_title_color()
            self.chevron.setVisible(True)
            self.hovered.emit(True)
        elif watched is self and event.type() == QEvent.Leave:
            self._hovered = False
            self._update_title_color()
            self.chevron.setVisible(self._expanded)
            self.hovered.emit(False)
        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        self._hovered = True
        self._update_title_color()
        self.chevron.setVisible(True)
        self.hovered.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_title_color()
        self.chevron.setVisible(self._expanded)
        self.hovered.emit(False)
        super().leaveEvent(event)

    @property
    def is_hovered(self) -> bool:
        return self._hovered

