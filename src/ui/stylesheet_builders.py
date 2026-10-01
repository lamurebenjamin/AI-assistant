"""Styles QSS builders ; tokens lus au moment de chaque appel."""

from src.ui.stylesheet_base import (
    qss_acrylic_panel,
    qss_buttons,
    qss_hairline,
    qss_header_icon_button,
    qss_inputs,
    qss_list_widget,
    qss_menu,
    qss_opaque_panel,
    qss_scrollbar,
    qss_tab_widget,
    qss_title_label,
    qss_tool_button,
    qss_tooltip,
)
from src.ui.stylesheet_settings import qss_settings_local


def build_acrylic_window_qss(font_offset: int = 0) -> str:
    """QSS complet pour fenêtres translucides (AssistantWindow, RecordingIndicator)."""
    return (
        qss_acrylic_panel()
        + qss_title_label(font_offset)
        + qss_header_icon_button("HeaderIconButton")
        + qss_hairline()
        + qss_scrollbar()
        + qss_tooltip()
        + qss_menu()
    )

def build_settings_qss() -> str:
    """QSS complet pour SettingsDialog."""
    return (
        qss_opaque_panel()
        + qss_settings_local()
        + qss_title_label()
        + qss_header_icon_button("CloseButton")
        + qss_hairline()
        + qss_tab_widget()
        + qss_tool_button()
        + qss_inputs()
        + qss_list_widget()
        + qss_buttons()
        + qss_scrollbar()
        + qss_tooltip()
        + qss_menu()
    )

def build_document_dialog_qss() -> str:
    """QSS de base pour DocumentDialog (styles spécifiques dans le fichier)."""
    return (
        qss_acrylic_panel()
        + qss_title_label()
        + qss_header_icon_button("HeaderIconButton")
        + qss_header_icon_button("CloseButton")
        + qss_hairline()
        + qss_scrollbar()
        + qss_inputs()
        + qss_buttons()
        + qss_tooltip()
        + qss_menu()
    )
