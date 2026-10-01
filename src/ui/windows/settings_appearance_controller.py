"""Apercu du theme et rafraichissement des styles."""
from PySide6.QtWidgets import QApplication

from src.ui.icons import ICONS, ICONS_DARK
from src.ui.stylesheet import build_settings_qss, qss_ctrl9_preview
from src.ui.theme import apply_app_theme
from src.ui.widgets.status_label import StatusLabel


def _on_theme_preview_changed(self, _index=None):
    new_theme = "dark" if self.theme_combo.currentIndex() == 0 else "light"
    app = QApplication.instance()
    if app:
        apply_app_theme(app, new_theme)
    else:
        self.refresh_theme()


def refresh_theme(self) -> None:
    self.setStyleSheet(build_settings_qss())
    if hasattr(self, "separator_wrapper"):
        self.separator_wrapper.refresh_theme()
    if hasattr(self, "header"):
        self.header.refresh_logo()
    for label in self.findChildren(StatusLabel):
        label.refresh_theme()
    if hasattr(self, "close_btn"):
        self.close_btn.setIcon(ICONS_DARK["close"])
    if hasattr(self, "btn_add"):
        self.btn_add.setIcon(ICONS_DARK["add"])
        self.btn_del.setIcon(ICONS_DARK["delete"])
        self.btn_up.setIcon(ICONS_DARK["up"])
        self.btn_down.setIcon(ICONS_DARK["down"])
    if hasattr(self, "btn_cancel"):
        self.btn_cancel.setIcon(ICONS_DARK["cancel"])
        self.btn_save.setIcon(ICONS["save"])
    if hasattr(self, "ctrl9_font_size_spin"):
        self._refresh_ctrl9_preview(self.ctrl9_font_size_spin.value())


def _refresh_ctrl9_preview(self, val=None):
    size = int(val if val is not None else self.ctrl9_font_size_spin.value())
    self.ctrl9_preview_label.setStyleSheet(qss_ctrl9_preview(size))
