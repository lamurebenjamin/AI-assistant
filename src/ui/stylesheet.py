# -*- coding: utf-8 -*-
"""Blocs QSS partagés entre toutes les fenêtres de l'application.

Chaque fonction retourne une chaîne QSS prête à être concaténée dans
un appel ``setStyleSheet()``. Utilise dynamiquement les tokens de
``src.ui.design_tokens`` selon le thème actif.
"""

import src.ui.design_tokens as t


# ─────────────────────────────────────────────────────────────────────────────
#  Blocs atomiques
# ─────────────────────────────────────────────────────────────────────────────

def qss_acrylic_panel() -> str:
    """Panneau principal translucide (acrylic)."""
    return f"""
        QFrame#AcrylicPanel {{
            background-color: {t.COLOR_BG_ACRYLIC};
            border: 1px solid {t.COLOR_BORDER_ACRYLIC};
            border-radius: {t.RADIUS_2XL};
        }}
        QFrame#Header {{
            background-color: transparent;
            border: none;
        }}
    """


def qss_title_label(font_offset: int = 0) -> str:
    """Label de titre dans le header (nom de la fenêtre / transcript)."""
    title_size = int(t.SIZE_LG.rstrip("px")) + font_offset
    return f"""
        QLabel#TitleLabel {{
            background: transparent;
            color: {t.COLOR_TEXT_PRIMARY};
            border: none;
            padding: 0;
            font-family: {t.FONT_DISPLAY};
            font-size: {title_size}px;
            font-weight: 700;
        }}
    """


def qss_header_icon_button(object_name: str = "HeaderIconButton") -> str:
    """Bouton icône dans le header (fermer, parler, copier…)."""
    return f"""
        QPushButton#{object_name} {{
            background-color: transparent;
            border: none;
            border-radius: {t.RADIUS_XL};
            padding: 0;
            margin: 0;
            text-align: center;
        }}
        QPushButton#{object_name}:hover,
        QPushButton#{object_name}:pressed {{
            background-color: {t.COLOR_HOVER_DARK};
            border: none;
            outline: none;
            border-radius: {t.RADIUS_XL};
        }}
        QPushButton#{object_name}:focus {{
            background-color: {t.COLOR_HOVER_DARK};
            border: 1px solid {t.COLOR_PRIMARY};
            outline: none;
            border-radius: {t.RADIUS_XL};
        }}
        QPushButton#{object_name}:disabled {{
            background-color: transparent;
        }}
    """


def qss_scrollbar() -> str:
    """Scrollbar verticale fine et discrète."""
    return f"""
        QScrollArea, QScrollArea QWidget, QScrollArea QViewport {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: {t.COLOR_SCROLLBAR_TRACK};
            width: {t.SCROLLBAR_WIDTH}px;
            margin: 0;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {t.COLOR_SCROLLBAR_THUMB};
            min-height: {t.SCROLLBAR_THUMB_MIN}px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {t.COLOR_SCROLLBAR_HOVER};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            height: 0;
            background: transparent;
        }}
    """


def qss_tooltip() -> str:
    """Style des infobulles."""
    return f"""
        QToolTip {{
            background-color: {t.COLOR_BG_SURFACE};
            color: {t.COLOR_TEXT_PRIMARY};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_SM};
            padding: 5px 8px;
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_MD};
        }}
    """


def qss_hairline() -> str:
    """Séparateur horizontal 1px sous les barres de titre."""
    return f"""
        QFrame#Hairline {{
            background: {t.COLOR_SEPARATOR};
            border: none;
            min-height: {t.HAIRLINE_HEIGHT}px;
            max-height: {t.HAIRLINE_HEIGHT}px;
        }}
    """


def qss_menu(
    object_name: str | None = None,
    *,
    font_size: str | None = None,
    selected_as_primary: bool = False,
    padding: int = 5,
) -> str:
    """Menu contextuel partagé (application, tray, compositeur, transcript)."""
    selector = f"QMenu#{object_name}" if object_name else "QMenu"
    size = font_size or t.SIZE_MD
    selected_bg = t.COLOR_PRIMARY if selected_as_primary else t.COLOR_PRIMARY_SUBTLE
    selected_fg = t.COLOR_TEXT_INVERSE if selected_as_primary else t.COLOR_TEXT_PRIMARY
    return f"""
        {selector} {{
            background-color: {t.COLOR_BG_SURFACE};
            color: {t.COLOR_TEXT_PRIMARY};
            border: 1px solid {t.COLOR_BORDER};
            padding: {padding}px;
            font-family: {t.FONT_TEXT};
            font-size: {size};
            border-radius: {t.RADIUS_SM};
        }}
        {selector}::item {{
            background-color: transparent;
            color: {t.COLOR_TEXT_PRIMARY};
            min-height: 20px;
            padding: 6px 28px 6px 10px;
            margin: 1px;
            border-radius: {t.RADIUS_SM};
        }}
        {selector}::item:selected {{
            background-color: {selected_bg};
            color: {selected_fg};
        }}
        {selector}::item:disabled {{
            color: {t.COLOR_TEXT_MUTED};
            background-color: transparent;
        }}
        {selector}::separator {{
            height: 1px;
            background-color: {t.COLOR_BORDER_SUBTLE};
            margin: 5px 8px;
        }}
        {selector}::icon {{ padding-left: 4px; }}
    """


def qss_inputs() -> str:
    """Champs de saisie : QLineEdit, QTextEdit, QComboBox, QSpinBox."""
    return f"""
        QLineEdit, QTextEdit, QComboBox, QSpinBox {{
            background-color: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_MD};
            padding: 7px 10px;
            color: {t.COLOR_TEXT_PRIMARY};
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_LG};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {t.COLOR_PRIMARY};
            background-color: {t.COLOR_BG_SURFACE};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            subcontrol-origin: border;
            width: {t.SPINBOX_BUTTON_WIDTH}px;
            background-color: transparent;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {t.COLOR_HOVER_DARK};
        }}
        QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
            color: {t.COLOR_TEXT_MUTED};
            background-color: {t.COLOR_BG_SUBTLE};
        }}
    """


def qss_list_widget() -> str:
    """QListWidget avec sélection bleue et survol discret."""
    return f"""
        QListWidget {{
            background-color: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_MD};
            padding: 4px;
            outline: none;
            color: {t.COLOR_TEXT_PRIMARY};
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_LG};
        }}
        QListWidget::item {{
            padding: 6px;
            border-radius: {t.RADIUS_SM};
        }}
        QListWidget::item:hover {{
            background-color: {t.COLOR_HOVER_DARK};
        }}
        QListWidget:focus {{
            border: 1px solid {t.COLOR_PRIMARY};
        }}
        QListWidget::item:selected {{
            background-color: {t.COLOR_PRIMARY};
            color: {t.COLOR_TEXT_INVERSE};
        }}
        QListWidget::item:disabled {{
            color: {t.COLOR_TEXT_MUTED};
        }}
    """


def qss_buttons() -> str:
    """Boutons standard, bouton principal (SaveBtn) et annulation (CancelBtn)."""
    return f"""
        QPushButton {{
            background-color: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_MD};
            padding: 6px 12px;
            color: {t.COLOR_TEXT_PRIMARY};
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_LG};
        }}
        QPushButton:hover  {{ background-color: {t.COLOR_HOVER_DARK}; }}
        QPushButton:pressed {{ background-color: {t.COLOR_PRESS_DARK}; }}
        QPushButton:focus {{
            border: 1px solid {t.COLOR_PRIMARY};
        }}
        QPushButton:disabled {{
            color: {t.COLOR_TEXT_MUTED};
            background-color: {t.COLOR_BG_SUBTLE};
            border-color: {t.COLOR_BORDER_SUBTLE};
        }}

        QPushButton#SaveBtn {{
            background-color: {t.COLOR_PRIMARY};
            color: {t.COLOR_TEXT_ACTIVE};
            border: 1px solid {t.COLOR_PRIMARY};
            border-radius: {t.RADIUS_LG};
            padding: 7px 18px;
            font-weight: 600;
        }}
        QPushButton#SaveBtn:hover  {{
            background-color: {t.COLOR_PRIMARY_HOVER};
            border-color: {t.COLOR_PRIMARY_HOVER};
        }}
        QPushButton#SaveBtn:pressed {{
            background-color: {t.COLOR_PRIMARY_ACTIVE};
            border-color: {t.COLOR_PRIMARY_ACTIVE};
        }}
        QPushButton#SaveBtn:disabled {{
            background-color: {t.COLOR_BG_SUBTLE};
            color: {t.COLOR_TEXT_MUTED};
            border-color: {t.COLOR_BORDER_SUBTLE};
        }}

        QPushButton#CancelBtn {{
            background-color: {t.COLOR_BG_SURFACE};
            color: {t.COLOR_TEXT_SECONDARY};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_LG};
            padding: 7px 16px;
            font-weight: 600;
        }}
        QPushButton#CancelBtn:hover  {{
            background-color: {t.COLOR_BG_SUBTLE};
            border-color: {t.COLOR_BORDER_STRONG};
        }}
        QPushButton#CancelBtn:pressed {{ background-color: {t.COLOR_BG_PAGE}; }}
        QPushButton#CancelBtn:disabled {{
            color: {t.COLOR_TEXT_MUTED};
            background-color: {t.COLOR_BG_SUBTLE};
            border-color: {t.COLOR_BORDER_SUBTLE};
        }}
    """


def qss_tool_button() -> str:
    """Bouton icône générique (ToolButton) avec effet de survol discret."""
    return f"""
        QPushButton#ToolButton {{
            background-color: transparent;
            border: none;
            border-radius: {t.RADIUS_XL};
            padding: 3px;
        }}
        QPushButton#ToolButton:hover   {{ background-color: {t.COLOR_HOVER_DARK}; }}
        QPushButton#ToolButton:pressed {{ background-color: {t.COLOR_PRESS_DARK}; }}
        QPushButton#ToolButton:focus {{
            background-color: {t.COLOR_HOVER_DARK};
            outline: none;
        }}
        QPushButton#ToolButton:disabled {{ background-color: transparent; }}
    """


def qss_tab_widget() -> str:
    """QTabWidget et QTabBar — onglets modernes style Windows 11 / Antigravity."""
    return f"""
        QTabWidget::pane {{
            background: {t.COLOR_BG_PAGE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_LG};
            top: 4px;
        }}
        QTabBar {{
            background: transparent;
            qproperty-drawBase: 0;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {t.COLOR_TEXT_SECONDARY};
            border: 1px solid transparent;
            border-radius: {t.RADIUS_MD};
            padding: 8px 18px;
            margin-right: 4px;
            font-weight: 600;
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_LG};
        }}
        QTabBar::tab:selected {{
            background: {t.COLOR_BG_SURFACE};
            color: {t.COLOR_PRIMARY};
            border: 1px solid {t.COLOR_BORDER};
        }}
        QTabBar::tab:hover:!selected {{
            background: {t.COLOR_HOVER_DARK};
            color: {t.COLOR_TEXT_PRIMARY};
        }}
    """


def qss_opaque_panel() -> str:
    """Panneau principal opaque (utilisé par SettingsDialog)."""
    return f"""
        QFrame#AcrylicPanel {{
            background-color: {t.COLOR_BG_PAGE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_2XL};
        }}
        QFrame#Header {{
            background-color: transparent;
            border: none;
        }}
        QDialog {{
            background-color: {t.COLOR_BG_PAGE};
        }}
        QLabel {{
            color: {t.COLOR_TEXT_PRIMARY};
            background: transparent;
        }}
    """


def qss_runtime_values() -> str:
    """Carte d'informations d'exécution (Ctrl+I)."""
    return f"""
        QDialog {{
            background: {t.COLOR_BG_PAGE};
        }}
        QLabel#RuntimeValues {{
            color: {t.COLOR_TEXT_PRIMARY};
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_LG};
            background: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_MD};
            padding: 14px;
        }}
    """


def qss_settings_local() -> str:
    """Styles de rôles propres à la fenêtre Paramètres."""
    return f"""
        QWidget#SettingsContent {{
            background-color: {t.COLOR_BG_PAGE};
        }}
        QLabel#SettingsHint {{
            color: {t.COLOR_TEXT_SECONDARY};
            font-size: {t.SIZE_XS};
            background: transparent;
        }}
        QLabel#SettingsHintItalic {{
            color: {t.COLOR_TEXT_SECONDARY};
            font-size: {t.SIZE_SM};
            font-style: italic;
            background: transparent;
        }}
        QFrame#SettingsCard {{
            background: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_BORDER_SUBTLE};
            border-radius: {t.RADIUS_LG};
        }}
    """


def qss_settings_emphasis(font_size: int | None = None, bold: bool = False) -> str:
    """Accent typographique pour les libellés de paramètres."""
    declarations = ["font-weight: 700;" if bold else "font-weight: 600;"]
    if font_size is not None:
        declarations.append(f"font-size: {int(font_size)}px;")
    return " ".join(declarations)


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


def qss_transparent_surface() -> str:
    """Surface interne sans fond ni bordure."""
    return "background: transparent; border: none;"


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


from src.ui.stylesheet_document import (
    qss_document_page_name, qss_document_page_editor, qss_document_page_dash,
    qss_ctrl9_preview, qss_document_dialog, qss_document_preview_dialog,
    qss_tool_call_step, qss_tool_code_browser,
)


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


def qss_assistant_body() -> str:
    """Corps de la fenêtre Transcript et bandeau d'outil."""
    size_lg = f"{int(t.SIZE_LG.rstrip('px')) + 1}px"
    size_sm = int(t.SIZE_SM.rstrip("px")) + 1
    return f"""
        QLabel#TranscriptBody {{
            background: transparent;
            color: {t.COLOR_TEXT_PRIMARY};
            padding: 10px 14px 10px 14px;
            font-family: {t.FONT_TEXT};
            font-size: {size_lg};
            line-height: 1.5;
        }}
        QLabel#ToolStatus {{
            background: {t.COLOR_SKILL_BACKGROUND};
            color: {t.COLOR_SKILL_TEXT};
            border: none;
            padding: 5px 10px;
            font-size: {size_sm};
            font-style: italic;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
#  Feuilles de style complètes par type de fenêtre
# ─────────────────────────────────────────────────────────────────────────────

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
