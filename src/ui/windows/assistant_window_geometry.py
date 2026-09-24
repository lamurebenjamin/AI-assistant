"""Gestion des géométries, masques arrondis et animations de la fenêtre assistant."""

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QRectF,
)
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QApplication


class AssistantWindowGeometryController:
    """Centralise les animations et la géométrie de la fenêtre flottante."""

    def __init__(self, host):
        self.host = host

    def update_rounded_mask(self):
        radius = 16.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.host.rect()), radius, radius)
        self.host.setMask(QRegion(path.toFillPolygon().toPolygon()))

        panel_path = QPainterPath(); panel_path.addRoundedRect(QRectF(self.host.panel.rect()), radius, radius)
        self.host.panel.setMask(QRegion(panel_path.toFillPolygon().toPolygon()))

    def resize_event(self, event):
        self.update_rounded_mask()
        return event

    def stop_height_animation(self):
        if self.host.collapse_animation is not None:
            self.host.collapse_animation.stop()
            self.host.collapse_animation.deleteLater()
            self.host.collapse_animation = None

    def calculate_expanded_height(self):
        self.host.label.adjustSize()
        thinking_height = (
            self.host.thinking_widget.sizeHint().height()
            if self.host.thinking_widget.isVisible()
            else 0
        )
        content_height = self.host.label.sizeHint().height() + thinking_height + 52
        maximum_height = max(150, int(self.host.width() * 9 / 16))
        return max(70, min(maximum_height, content_height))

    def animate_height(self, target, expanding):
        host = self.host
        self.stop_height_animation()
        current = host.geometry()
        fixed_top = current.top()

        host.is_collapsed = not expanding
        if expanding:
            host.separator_container.show()
            host.scroll_area.show()
            target = max(70, target)
        else:
            host.expanded_height = self.calculate_expanded_height()
            target = 38

        animation = QPropertyAnimation(host, b"geometry", host)
        host.collapse_animation = animation
        animation.setDuration(300)
        animation.setStartValue(current)
        animation.setEndValue(QRect(current.left(), fixed_top, current.width(), target))
        animation.setEasingCurve(QEasingCurve.InOutCubic)

        def done():
            if host.collapse_animation is not animation:
                return
            host.collapse_animation = None
            if expanding:
                host.resize(host.width(), target)
                host.separator_container.show()
                host.scroll_area.show()
            else:
                host.separator_container.hide()
                host.scroll_area.hide()
            host.move(host.x(), fixed_top)
            self.update_rounded_mask()
            animation.deleteLater()

        animation.finished.connect(done)
        animation.start()

    def show_window(self, preserve_position=False):
        host = self.host
        previous_position = host.pos()
        self.stop_height_animation()
        host.separator_container.show()
        host.scroll_area.show()
        host.is_collapsed = False

        host.expanded_height = self.calculate_expanded_height()
        host.resize(host.width(), host.expanded_height)

        cursor_pos = QApplication.cursor().pos() if hasattr(QApplication, 'cursor') else None
        if cursor_pos is None:
            cursor_pos = host.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        x = cursor_pos.x()
        y = cursor_pos.y() + 20
        if x + host.width() > screen_rect.right() - 10:
            x = screen_rect.right() - host.width() - 10
        x = max(x, screen_rect.left() + 10)
        if y + host.height() > screen_rect.bottom() - 10:
            y = cursor_pos.y() - host.height() - 20
        y = max(y, screen_rect.top() + 10)
        if preserve_position and host.isVisible():
            host.move(previous_position)
        else:
            host.move(x, y)
        host.show()
