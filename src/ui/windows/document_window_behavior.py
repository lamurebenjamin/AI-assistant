"""Deplacement, repli et effets visuels de la fenetre documentaire."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QRectF, Qt
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QApplication

import src.ui.design_tokens as t
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners


def _header_press(self,event):
    if event.button()==Qt.LeftButton:
        self._drag_position=event.globalPos()-self.frameGeometry().topLeft(); self._header_press_pos=event.globalPos(); self._header_was_dragged=False; event.accept()


def _header_move(self,event):
    if self._drag_position is not None and event.buttons() & Qt.LeftButton:
        if self._header_press_pos is not None and (event.globalPos()-self._header_press_pos).manhattanLength()>QApplication.startDragDistance(): self._header_was_dragged=True
        if self._header_was_dragged: self.move(event.globalPos()-self._drag_position)
        event.accept()


def _header_release(self,event):
    if event.button()==Qt.LeftButton:
        if not self._header_was_dragged: self.toggle_collapse()
        self._drag_position=None; self._header_press_pos=None; self._header_was_dragged=False; event.accept()


def toggle_collapse(self):
    if self.collapse_animation is not None:
        self.collapse_animation.stop()
        self.collapse_animation.deleteLater()
        self.collapse_animation = None

    current = self.height()
    collapsed_height = 38
    self.setMinimumHeight(collapsed_height)
    if self.is_collapsed:
        target = max(self.MIN_HEIGHT, self.expanded_height)
        self.separator_container.show()
        self.content_widget.show()
        expanding = True
    else:
        self.expanded_height = max(self.MIN_HEIGHT, current)
        self.separator_container.hide()
        target = collapsed_height
        expanding = False

    animation = QPropertyAnimation(self, b"geometry", self)
    animation.setDuration(180)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.setStartValue(self.geometry())
    animation.setEndValue(QRect(self.x(), self.y(), self.width(), target))
    self.collapse_animation = animation

    def done():
        if self.collapse_animation is not animation:
            return
        self.collapse_animation = None
        self.is_collapsed = not expanding
        if expanding:
            self.setMinimumHeight(self.MIN_HEIGHT)
        else:
            self.content_widget.hide()
        animation.deleteLater()

    animation.finished.connect(done)
    animation.start()


def _update_rounded_masks(self):
    radius = max(1, int(t.RADIUS_2XL.rstrip("px")))
    path = QPainterPath()
    path.addRoundedRect(QRectF(self.rect()), radius, radius)
    self.setMask(QRegion(path.toFillPolygon().toPolygon()))
    if hasattr(self, "panel"):
        panel_path = QPainterPath()
        panel_path.addRoundedRect(QRectF(self.panel.rect()), radius, radius)
        self.panel.setMask(QRegion(panel_path.toFillPolygon().toPolygon()))


def _apply_effects(self):
    # Applique le flou DWM après la création du HWND. Un seul arrondi est
    # dessiné par Qt sur DocPanel : l'arrondi DWM natif est volontairement
    # désactivé pour éviter un second rayon différent.
    if self.windowHandle() is None:
        return
    self._update_rounded_masks()
    apply_acrylic_blur(int(self.winId()))
    apply_rounded_corners(int(self.winId()))
