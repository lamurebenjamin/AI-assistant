"""Styles QSS conversation ; tokens lus au moment de chaque appel."""

import src.ui.design_tokens as t
from src.ui.stylesheet_base import qss_transparent_surface


def qss_response_scroll_area() -> str:
    """Surface de conversation sans bordure ni marges internes."""
    return """
        QScrollArea#Response {
            background: transparent;
            border: none;
            padding: 0;
            margin: 0;
        }
        QScrollArea#Response>QWidget>QWidget {
            background: transparent;
            border: none;
            margin: 0;
            padding: 0;
        }
        QScrollArea#Response QScrollBar:vertical {
            margin: 0;
        }
    """

def qss_turn_navigation() -> str:
    """Navigation compacte entre les tours de conversation."""
    return f"""
        QFrame#TurnNavigation {{
            background: transparent;
            border: none;
            border-radius: {t.RADIUS_MD};
        }}
        QFrame#TurnNavigation:hover {{
            background: transparent;
        }}
        QFrame#TurnNavigation QPushButton {{
            color: {t.COLOR_TEXT_MUTED};
            background: transparent;
            border: none;
            font-size: {t.SIZE_XS};
            padding: 0;
        }}
        QFrame#TurnNavigation QPushButton:hover,
        QFrame#TurnNavigation QPushButton:checked {{
            color: {t.COLOR_PRIMARY};
            font-size: {t.SIZE_MD};
        }}
    """

def qss_slash_popup() -> str:
    """Surface et états de la palette de commandes slash."""
    return f"""
        QFrame#SlashCommandPopup {{
            background-color: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_XL};
        }}
        QListWidget {{
            background: transparent;
            border: none;
            outline: none;
            padding: 2px;
        }}
        QListWidget::item {{
            border-radius: {t.RADIUS_MD};
            margin: 1px 4px;
        }}
        QListWidget::item:hover {{
            background-color: {t.COLOR_OVERLAY_HOVER};
        }}
        QListWidget::item:selected {{
            background-color: {t.COLOR_OVERLAY_SELECTED};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 5px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {t.COLOR_SCROLLBAR_THUMB};
            border-radius: {t.RADIUS_XS};
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
            background: transparent;
        }}
    """

def qss_slash_command_label() -> str:
    """Libellé principal d'une commande slash."""
    command_color = t.COLOR_TEXT_PRIMARY if t.is_dark_theme() else t.COLOR_PRIMARY
    return f"""
        font-family: {t.FONT_TEXT};
        font-size: {t.SIZE_SM};
        font-weight: 700;
        color: {command_color};
        background: transparent;
    """

def qss_slash_description() -> str:
    """Description secondaire d'une commande slash."""
    return f"""
        font-family: {t.FONT_TEXT};
        font-size: {t.SIZE_XS};
        color: {t.COLOR_TEXT_SECONDARY};
        background: transparent;
    """

def qss_slash_header() -> str:
    """Titre de section de la palette slash."""
    return f"""
        font-family: {t.FONT_TEXT};
        font-size: {t.SIZE_XS};
        font-weight: 700;
        color: {t.COLOR_TEXT_MUTED};
        padding: 2px 8px;
        background: transparent;
    """

def qss_document_attachment_scroll() -> str:
    """Barre de défilement horizontale de la zone des pièces jointes."""
    return f"""
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea>QWidget>QWidget {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            height: 7px;
            background: transparent;
            margin: 0 6px 1px 6px;
        }}
        QScrollBar::handle:horizontal {{
            background: {t.COLOR_SCROLLBAR_HORIZONTAL};
            border-radius: {t.RADIUS_XS};
            min-width: 24px;
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
            border: none;
        }}
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
    """

def qss_slash_icon_label() -> str:
    """Icône de menu slash transparente."""
    return f"font-size: 14px; {qss_transparent_surface()}"
