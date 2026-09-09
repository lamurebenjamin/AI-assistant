"""Gestion du thème visuel : acrylique Windows, coins arrondis, palette claire."""

import ctypes
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette


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
    palette.setColor(QPalette.Window, QColor("#F8FAFC"))
    palette.setColor(QPalette.WindowText, QColor("#111111"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F1F5F9"))
    palette.setColor(QPalette.Text, QColor("#111111"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#111111"))
    palette.setColor(QPalette.Highlight, QColor("#DCEBFF"))
    palette.setColor(QPalette.HighlightedText, QColor("#111111"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipText, QColor("#111111"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#8A949F"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#8A949F"))
    app.setPalette(palette)
    app.setStyleSheet(
        (app.styleSheet() or "")
        + """
        QMenu {
            background-color: #FFFFFF;
            color: #111111;
            border: 1px solid #CBD7E4;
            padding: 5px;
            font-family: 'Segoe UI Variable', 'Segoe UI', Arial;
            font-size: 12px;
        }
        QMenu::item {
            background-color: transparent;
            color: #111111;
            min-height: 20px;
            padding: 6px 28px 6px 10px;
            margin: 1px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: #DCEBFF;
            color: #111111;
        }
        QMenu::item:disabled {
            color: #8A949F;
            background-color: transparent;
        }
        QMenu::separator {
            height: 1px;
            background-color: #D7E0EA;
            margin: 5px 8px;
        }
        QMenu::icon { padding-left: 4px; }
        QToolTip {
            background-color: #FFFFFF;
            color: #111111;
            border: 1px solid #CBD7E4;
            padding: 4px 7px;
        }
    """
    )
