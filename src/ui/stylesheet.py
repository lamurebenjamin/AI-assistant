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


def qss_title_label() -> str:
    """Label de titre dans le header (nom de la fenêtre / transcript)."""
    return f"""
        QLabel#TitleLabel {{
            background: transparent;
            color: {t.COLOR_TEXT_PRIMARY};
            border: none;
            padding: 0;
            font-family: {t.FONT_DISPLAY};
            font-size: {t.SIZE_LG};
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
        QPushButton#{object_name}:pressed,
        QPushButton#{object_name}:focus {{
            background-color: {t.COLOR_HOVER_DARK};
            border: none;
            outline: none;
            border-radius: {t.RADIUS_XL};
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
            width: 6px;
            margin: 0;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {t.COLOR_SCROLLBAR_THUMB};
            min-height: 26px;
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


def qss_inputs() -> str:
    """Champs de saisie : QLineEdit, QTextEdit, QComboBox."""
    return f"""
        QLineEdit, QTextEdit, QComboBox {{
            background-color: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_MD};
            padding: 7px 10px;
            color: {t.COLOR_TEXT_PRIMARY};
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_LG};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: 1px solid {t.COLOR_PRIMARY};
            background-color: {t.COLOR_BG_SURFACE};
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
        QListWidget::item:selected {{
            background-color: {t.COLOR_PRIMARY};
            color: {t.COLOR_TEXT_INVERSE};
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

        QPushButton#SaveBtn {{
            background-color: {t.COLOR_PRIMARY};
            color: #FFFFFF;
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
        QPushButton#CancelBtn:pressed {{ background-color: {t.COLOR_GRAY_300}; }}
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
