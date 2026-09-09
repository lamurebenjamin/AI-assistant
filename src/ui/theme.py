"""Gestion du thème visuel : acrylique Windows, coins arrondis, palette claire."""

import ctypes
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette

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
)


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


def apply_acrylic_blur(hwnd: int, color: int = 0xA0F8F8F8) -> bool:
    """Applique un fond acrylique blanc translucide sous Windows 10/11."""
    if sys.platform != "win32":
        return False

    try:
        accent = AccentPolicy()
        accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.GradientColor = color  # Format Windows : AABBGGRR (0x40 = ~25% d'opacité)
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


def apply_rounded_corners(hwnd: int) -> None:
    """Active les coins arrondis natifs sous Windows 11."""
    if sys.platform != "win32":
        return

    try:
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(hwnd), 33, ctypes.byref(preference), ctypes.sizeof(preference)
        )
    except (AttributeError, OSError):
        pass


def apply_light_popup_theme(app) -> None:
    """Force les menus Qt, y compris Copier/Coller, en thème clair.

    Les menus contextuels standards de QTextEdit/QTextBrowser sont créés par Qt
    au moment du clic droit. Un style local sur la fenêtre ne suffit donc pas :
    la palette et le QSS doivent être appliqués au niveau de QApplication.
    """
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
    palette.setColor(QPalette.ToolTipBase, QColor(COLOR_BG_SURFACE))
    palette.setColor(QPalette.ToolTipText, QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(COLOR_TEXT_MUTED))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(COLOR_TEXT_MUTED))
    app.setPalette(palette)
    app.setStyleSheet(
        (app.styleSheet() or "")
        + f"""
        QMenu {{
            background-color: {COLOR_BG_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            padding: 5px;
            font-family: {FONT_TEXT};
            font-size: {SIZE_MD};
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
            background-color: {COLOR_PRIMARY_LIGHT};
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
            background-color: #FFFFFF;
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 0px;
            padding: 5px 8px;
            font-family: {FONT_TEXT};
            font-size: {SIZE_MD};
        }}
    """
    )
