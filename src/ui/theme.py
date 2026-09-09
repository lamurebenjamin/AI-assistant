"""Gestion du thème visuel : acrylique Windows, coins arrondis, palette Antigravity."""

import ctypes
import sys
from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QToolTip


class AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_uint),
    ]


class WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_uint),
        ("Data", ctypes.POINTER(AccentPolicy)),
        ("SizeOfData", ctypes.c_int),
    ]


def apply_acrylic_blur(hwnd: int, color: int = None) -> bool:
    """Applique un fond acrylique translucide sous Windows 10/11 adapté au thème actif."""
    if sys.platform != "win32":
        return False

    if color is None:
        from src.ui.design_tokens import is_dark_theme
        color = 0xEB1E1E1E if is_dark_theme() else 0xA0F8F8F8

    try:
        accent = AccentPolicy()
        accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.GradientColor = color  # Format Windows : AABBGGRR
        accent.AccentFlags = 2
        accent.AnimationId = 0

        data = WindowCompositionAttributeData()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        result = ctypes.windll.user32.SetWindowCompositionAttribute(
            int(hwnd), ctypes.byref(data)
        )
        return bool(result)
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def apply_rounded_corners(hwnd: int, round_type: int = 2) -> None:
    """Active les coins arrondis natifs sous Windows 11 (DWMWCP_ROUND = 2)."""
    if sys.platform != "win32":
        return

    try:
        preference = ctypes.c_int(round_type)  # 2 = DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(hwnd), 33, ctypes.byref(preference), ctypes.sizeof(preference)
        )
    except (AttributeError, OSError):
        pass


class CleanToolTipFilter(QObject):
    """Évite le bug de rectangle noir sous Windows sur fenêtres translucides."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.ToolTip:
            text = watched.toolTip() if hasattr(watched, "toolTip") else ""
            if text:
                QToolTip.showText(event.globalPos(), text, None)
                return True
        return super().eventFilter(watched, event)


def apply_app_theme(app, theme_name: str = None) -> None:
    """Applique le thème (palette Qt, menus, tooltips, icônes) à l'application entière."""
    from src.ui.design_tokens import (
        COLOR_BG_PAGE,
        COLOR_BG_SUBTLE,
        COLOR_BG_SURFACE,
        COLOR_BORDER,
        COLOR_BORDER_SUBTLE,
        COLOR_PRIMARY_LIGHT,
        COLOR_TEXT_MUTED,
        COLOR_TEXT_PRIMARY,
        FONT_TEXT,
        RADIUS_SM,
        SIZE_MD,
        is_dark_theme,
        set_active_theme,
    )
    from src.ui.icons import update_icons_for_theme

    if theme_name:
        set_active_theme(theme_name)

    is_dark = is_dark_theme()
    update_icons_for_theme(is_dark)

    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(COLOR_BG_PAGE))
    palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(COLOR_BG_SURFACE))
    palette.setColor(QPalette.AlternateBase, QColor(COLOR_BG_SUBTLE))
    palette.setColor(QPalette.Text, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(COLOR_BG_SURFACE))
    palette.setColor(QPalette.ButtonText, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(COLOR_PRIMARY_LIGHT))
    palette.setColor(QPalette.HighlightedText, QColor(COLOR_TEXT_PRIMARY))
    tooltip_bg = "#1F1F1F" if is_dark else "#FFFFFF"
    palette.setColor(QPalette.ToolTipBase, QColor(tooltip_bg))
    palette.setColor(QPalette.ToolTipText, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(COLOR_TEXT_MUTED))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(COLOR_TEXT_MUTED))
    app.setPalette(palette)

    menu_selected_bg = "rgba(56, 139, 253, 35)" if is_dark else COLOR_PRIMARY_LIGHT
    tooltip_bg_qss = "#1F1F1F" if is_dark else "#FFFFFF"
    tooltip_border = "#3C3C3C" if is_dark else COLOR_BORDER

    app.setStyleSheet(
        f"""
        QMenu {{
            background-color: {COLOR_BG_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            padding: 5px;
            font-family: {FONT_TEXT};
            font-size: {SIZE_MD};
            border-radius: {RADIUS_SM};
        }}
        QMenu::item {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            min-height: 20px;
            padding: 6px 28px 6px 10px;
            margin: 1px;
            border-radius: {RADIUS_SM};
        }}
        QMenu::item:selected {{
            background-color: {menu_selected_bg};
            color: {COLOR_TEXT_PRIMARY};
        }}
        QMenu::item:disabled {{
            color: {COLOR_TEXT_MUTED};
            background-color: transparent;
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {COLOR_BORDER_SUBTLE};
            margin: 5px 8px;
        }}
        QMenu::icon {{ padding-left: 4px; }}
        QToolTip {{
            background-color: {tooltip_bg_qss};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {tooltip_border};
            border-radius: {RADIUS_SM};
            padding: 5px 8px;
            font-family: {FONT_TEXT};
            font-size: {SIZE_MD};
        }}
    """
    )
    if not hasattr(app, "_clean_tooltip_filter"):
        app._clean_tooltip_filter = CleanToolTipFilter(app)
        app.installEventFilter(app._clean_tooltip_filter)


def apply_light_popup_theme(app) -> None:
    """Compatibilité avec l'ancien nom de fonction : applique le thème actif."""
    apply_app_theme(app)
