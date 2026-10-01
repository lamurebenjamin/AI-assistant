"""Styles QSS settings ; tokens lus au moment de chaque appel."""

import src.ui.design_tokens as t


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
