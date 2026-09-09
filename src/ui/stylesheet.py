# -*- coding: utf-8 -*-
"""Blocs QSS partagés entre toutes les fenêtres de l'application.

Chaque fonction retourne une chaîne QSS prête à être concaténée dans
un appel ``setStyleSheet()``. Aucune valeur n'est hardcodée : toutes
les références passent par ``src.ui.design_tokens``.

Usage typique::

    from src.ui.stylesheet import build_window_qss

    self.setStyleSheet(
        build_window_qss()
        + qss_window_specific_rules()
    )
"""

from src.ui.design_tokens import (
    COLOR_BG_PAGE,
    COLOR_BG_SUBTLE,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_INPUT,
    COLOR_BORDER_STRONG,
    COLOR_BORDER_SUBTLE,
    COLOR_BG_ACRYLIC,
    COLOR_BORDER_ACRYLIC,
    COLOR_HOVER_DARK,
    COLOR_PRESS_DARK,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_PRIMARY_ACTIVE,
    COLOR_SCROLLBAR_HOVER,
    COLOR_SCROLLBAR_THUMB,
    COLOR_SCROLLBAR_TRACK,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_INVERSE,
    COLOR_GRAY_200,
    COLOR_GRAY_300,
    FONT_DISPLAY,
    FONT_TEXT,
    RADIUS_SM,
    RADIUS_MD,
    RADIUS_LG,
    RADIUS_XL,
    RADIUS_2XL,
    SIZE_LG,
    SIZE_MD,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Blocs atomiques
# ─────────────────────────────────────────────────────────────────────────────

def qss_acrylic_panel() -> str:
    """Panneau principal translucide (acrylic).

    Commun à AssistantWindow, SettingsDialog, DocumentDialog,
    RecordingIndicator et RuntimeInfoDialog.
    """
    return f"""
        QFrame#AcrylicPanel {{
            background-color: {COLOR_BG_ACRYLIC};
            border: 1px solid {COLOR_BORDER_ACRYLIC};
            border-radius: {RADIUS_2XL};
        }}
        QFrame#Header {{
            background-color: transparent;
            border: none;
        }}
    """


def qss_title_label() -> str:
    """Label de titre dans le header (nom de la fenêtre / transcript)."""
    return f"""
        QLabel#TitleLabel {{
            background: transparent;
            color: {COLOR_TEXT_PRIMARY};
            border: none;
            padding: 0;
            font-family: {FONT_DISPLAY};
            font-size: {SIZE_LG};
            font-weight: 700;
        }}
    """


def qss_header_icon_button(object_name: str = "HeaderIconButton") -> str:
    """Bouton icône dans le header (fermer, parler, copier…)."""
    return f"""
        QPushButton#{object_name} {{
            background-color: transparent;
            border: none;
            border-radius: {RADIUS_XL};
            padding: 0;
            margin: 0;
            text-align: center;
        }}
        QPushButton#{object_name}:hover,
        QPushButton#{object_name}:pressed,
        QPushButton#{object_name}:focus {{
            background-color: {COLOR_HOVER_DARK};
            border: none;
            outline: none;
            border-radius: {RADIUS_XL};
        }}
    """


def qss_scrollbar() -> str:
    """Scrollbar verticale fine et discrète — style Windows 11.

    À utiliser dans tous les panneaux avec défilement.
    """
    return f"""
        QScrollArea, QScrollArea QWidget, QScrollArea QViewport {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 0;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLOR_SCROLLBAR_THUMB};
            min-height: 26px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLOR_SCROLLBAR_HOVER};
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
    """Style des infobulles : fond blanc opaque, texte sombre, bordure sans artefact noir sous Windows."""
    return f"""
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


def qss_inputs() -> str:
    """Champs de saisie : QLineEdit, QTextEdit, QComboBox."""
    return f"""
        QLineEdit, QTextEdit, QComboBox {{
            background-color: {COLOR_BG_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-radius: {RADIUS_MD};
            padding: 7px 10px;
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_TEXT};
            font-size: {SIZE_LG};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: 1px solid {COLOR_PRIMARY};
            background-color: #FFFFFF;
        }}
    """


def qss_list_widget() -> str:
    """QListWidget avec sélection bleue et survol discret."""
    return f"""
        QListWidget {{
            background-color: rgba(255,255,255,245);
            border: 1px solid {COLOR_BORDER_INPUT};
            border-radius: {RADIUS_MD};
            padding: 4px;
            outline: none;
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_TEXT};
            font-size: {SIZE_LG};
        }}
        QListWidget::item {{
            padding: 6px;
            border-radius: {RADIUS_SM};
        }}
        QListWidget::item:hover {{
            background-color: {COLOR_HOVER_DARK};
        }}
        QListWidget::item:selected {{
            background-color: {COLOR_PRIMARY};
            color: {COLOR_TEXT_INVERSE};
        }}
    """


def qss_buttons() -> str:
    """Boutons standard, bouton principal (SaveBtn) et annulation (CancelBtn)."""
    return f"""
        QPushButton {{
            background-color: rgba(255,255,255,100);
            border: 1px solid rgba(0,0,0,50);
            border-radius: {RADIUS_MD};
            padding: 6px 12px;
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_TEXT};
            font-size: {SIZE_LG};
        }}
        QPushButton:hover  {{ background-color: {COLOR_HOVER_DARK}; }}
        QPushButton:pressed {{ background-color: {COLOR_PRESS_DARK}; }}

        QPushButton#SaveBtn {{
            background-color: {COLOR_PRIMARY};
            color: {COLOR_TEXT_INVERSE};
            border: 1px solid {COLOR_PRIMARY};
            border-radius: {RADIUS_LG};
            padding: 7px 18px;
            font-weight: 600;
        }}
        QPushButton#SaveBtn:hover  {{
            background-color: {COLOR_PRIMARY_HOVER};
            border-color: {COLOR_PRIMARY_HOVER};
        }}
        QPushButton#SaveBtn:pressed {{
            background-color: {COLOR_PRIMARY_ACTIVE};
            border-color: {COLOR_PRIMARY_ACTIVE};
        }}

        QPushButton#CancelBtn {{
            background-color: {COLOR_BG_SURFACE};
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: {RADIUS_LG};
            padding: 7px 16px;
            font-weight: 600;
        }}
        QPushButton#CancelBtn:hover  {{
            background-color: {COLOR_BG_SUBTLE};
            border-color: {COLOR_BORDER_STRONG};
        }}
        QPushButton#CancelBtn:pressed {{ background-color: {COLOR_GRAY_300}; }}
    """


def qss_tool_button() -> str:
    """Bouton icône générique (ToolButton) avec effet de survol discret."""
    return f"""
        QPushButton#ToolButton {{
            background-color: transparent;
            border: none;
            border-radius: {RADIUS_XL};
            padding: 3px;
        }}
        QPushButton#ToolButton:hover   {{ background-color: {COLOR_HOVER_DARK}; }}
        QPushButton#ToolButton:disabled {{ background-color: transparent; }}
    """


def qss_tab_widget() -> str:
    """QTabWidget et QTabBar — onglets modernes style Windows 11 Settings."""
    return f"""
        QTabWidget::pane {{
            background: {COLOR_BG_PAGE};
            border: 1px solid {COLOR_BORDER};
            border-radius: {RADIUS_LG};
            top: 4px;
        }}
        QTabBar {{
            background: transparent;
            qproperty-drawBase: 0;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid transparent;
            border-radius: {RADIUS_MD};
            padding: 8px 18px;
            margin-right: 4px;
            font-weight: 600;
            font-family: {FONT_TEXT};
            font-size: {SIZE_LG};
        }}
        QTabBar::tab:selected {{
            background: {COLOR_BG_SURFACE};
            color: {COLOR_PRIMARY};
            border: 1px solid {COLOR_BORDER};
        }}
        QTabBar::tab:hover:!selected {{
            background: {COLOR_HOVER_DARK};
            color: {COLOR_TEXT_PRIMARY};
        }}
    """


def qss_opaque_panel() -> str:
    """Panneau principal opaque (utilisé par SettingsDialog)."""
    return f"""
        QFrame#AcrylicPanel {{
            background-color: {COLOR_BG_PAGE};
            border: 1px solid {COLOR_BORDER};
            border-radius: {RADIUS_2XL};
        }}
        QFrame#Header {{
            background-color: transparent;
            border: none;
        }}
        QDialog {{
            background-color: {COLOR_BG_PAGE};
        }}
        QLabel {{
            color: {COLOR_TEXT_PRIMARY};
            background: transparent;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
#  Feuilles de style complètes par type de fenêtre
# ─────────────────────────────────────────────────────────────────────────────

def build_acrylic_window_qss() -> str:
    """QSS complet pour fenêtres translucides (AssistantWindow, RecordingIndicator)."""
    return (
        qss_acrylic_panel()
        + qss_title_label()
        + qss_header_icon_button("HeaderIconButton")
        + qss_scrollbar()
        + qss_tooltip()
    )


def build_settings_qss() -> str:
    """QSS complet pour SettingsDialog."""
    return (
        qss_opaque_panel()
        + qss_title_label()
        + qss_header_icon_button("CloseButton")
        + qss_tab_widget()
        + qss_tool_button()
        + qss_inputs()
        + qss_list_widget()
        + qss_buttons()
        + qss_scrollbar()
        + qss_tooltip()
    )


def build_document_dialog_qss() -> str:
    """QSS de base pour DocumentDialog (styles spécifiques dans le fichier)."""
    return (
        qss_acrylic_panel()
        + qss_title_label()
        + qss_header_icon_button("HeaderIconButton")
        + qss_header_icon_button("CloseButton")
        + qss_scrollbar()
        + qss_inputs()
        + qss_buttons()
        + qss_tooltip()
    )
