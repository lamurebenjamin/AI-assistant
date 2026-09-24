"""Gestion du thème visuel : Fluent Windows 11, coins arrondis, palette Antigravity."""

import ctypes
import sys

from PySide6.QtGui import QColor, QPalette
from qfluentwidgets import (
    SystemThemeListener,
    Theme,
    setTheme,
    setThemeColor,
)

# ─── Acrylic / Mica via ctypes (fallback pour fenêtres frameless custom) ─────

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


def apply_acrylic_blur(hwnd: int, color: int | None = None) -> bool:
    """Applique un acrylique Windows réellement translucide sous Windows 10/11."""
    if sys.platform != "win32":
        return False

    if color is None:
        from src.ui.design_tokens import (
            ACRYLIC_NATIVE_DARK,
            ACRYLIC_NATIVE_LIGHT,
            is_dark_theme,
        )
        color = ACRYLIC_NATIVE_DARK if is_dark_theme() else ACRYLIC_NATIVE_LIGHT

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





# ─── Thème principal via QFluentWidgets ───────────────────────────────────────

def apply_app_theme(app, theme_name: str | None = None) -> None:
    """Applique le thème QFluentWidgets + palette Qt à l'application entière.

    QFluentWidgets gère nativement Mica/Acrylic, les couleurs d'accent Windows 11
    et la synchronisation automatique avec le thème système via SystemThemeListener.
    """
    import src.ui.design_tokens as t
    from src.ui.icons import update_icons_for_theme
    from src.ui.stylesheet import qss_menu, qss_tooltip

    if getattr(app, "_theme_refresh_running", False) and not theme_name:
        return

    if theme_name:
        t.set_active_theme(theme_name)
        # Synchroniser QFluentWidgets avec notre token
        qfw_theme = Theme.DARK if t.is_dark_theme() else Theme.LIGHT
        setTheme(qfw_theme, lazy=True)
        # Couleur d'accent = bleu Antigravity
        setThemeColor(QColor(t.COLOR_PRIMARY), lazy=True)

    is_dark = t.is_dark_theme()
    update_icons_for_theme(is_dark)

    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(t.COLOR_BG_PAGE))
    palette.setColor(QPalette.WindowText, QColor(t.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(t.COLOR_BG_SURFACE))
    palette.setColor(QPalette.AlternateBase, QColor(t.COLOR_BG_SUBTLE))
    palette.setColor(QPalette.Text, QColor(t.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(t.COLOR_BG_SURFACE))
    palette.setColor(QPalette.ButtonText, QColor(t.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(t.COLOR_PRIMARY_LIGHT))
    palette.setColor(QPalette.HighlightedText, QColor(t.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ToolTipBase, QColor(t.COLOR_BG_SURFACE))
    palette.setColor(QPalette.ToolTipText, QColor(t.COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(t.COLOR_TEXT_MUTED))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(t.COLOR_TEXT_MUTED))
    app.setPalette(palette)

    app.setStyleSheet(qss_menu() + qss_tooltip())

    app._theme_refresh_running = True
    try:
        refresh_open_windows(app)
    finally:
        app._theme_refresh_running = False


def refresh_open_windows(app) -> None:
    """Relit les tokens sur les fenêtres déjà ouvertes."""
    for widget in app.topLevelWidgets():
        refresh = getattr(widget, "refresh_theme", None)
        if callable(refresh):
            refresh()


def apply_light_popup_theme(app) -> None:
    """Compatibilité avec l'ancien nom de fonction : applique le thème actif."""
    apply_app_theme(app)


def install_system_theme_listener(app) -> "SystemThemeListener | None":
    """Installe le listener QFluentWidgets pour synchroniser le thème Windows 11.

    Retourne le listener (à conserver en vie sur l'objet app).
    """
    try:
        listener = SystemThemeListener(app)
        listener.start()
        return listener
    except Exception:  # noqa: BLE001
        return None
