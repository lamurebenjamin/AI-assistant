"""QSS rules dedicated to document previews and dialogs."""

import src.ui.design_tokens as t


def qss_document_page_name(font_offset: int = 0) -> str:
    """Nom de fichier affiché sous une vignette documentaire."""
    return f"""
        background: transparent;
        border: none;
        color: {t.COLOR_TEXT_SECONDARY};
        font-family: {t.FONT_TEXT};
        font-size: {int(t.SIZE_XS.rstrip('px')) + font_offset}px;
        font-weight: 600;
        padding: 0;
        margin: 0;
    """


def qss_document_page_editor(font_offset: int = 0) -> str:
    """Éditeur compact de plage de pages."""
    return f"""
        QLineEdit {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: {t.RADIUS_SM};
            padding: 0;
            margin: 0;
            font-family: {t.FONT_TEXT};
            font-size: {int(t.SIZE_XS.rstrip('px')) + font_offset}px;
        }}
        QLineEdit:hover {{
            background: {t.COLOR_INLINE_EDIT_HOVER};
            border: 1px solid {t.COLOR_INLINE_EDIT_BORDER};
        }}
        QLineEdit:focus {{
            background: {t.COLOR_BG_SURFACE};
            border: 1px solid {t.COLOR_INLINE_EDIT_FOCUS};
        }}
    """


def qss_document_page_dash(font_offset: int = 0) -> str:
    """Séparateur de plage de pages."""
    return f"""
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
        font-family: {t.FONT_TEXT};
        font-size: {int(t.SIZE_XS.rstrip('px')) + font_offset}px;
    """


def qss_ctrl9_preview(font_size: int) -> str:
    """Aperçu de taille de police dans l'onglet Ctrl+9."""
    return (
        f"background: {t.COLOR_PREVIEW_DASHED}; border: 1px dashed {t.COLOR_BORDER}; "
        f"border-radius: {t.RADIUS_MD}; padding: 8px; font-size: {int(font_size)}px; "
        f"color: {t.COLOR_TEXT_PRIMARY}; font-family: {t.FONT_TEXT};"
    )


def qss_document_dialog(font_offset: int = 0) -> str:
    """Feuille Ctrl+9 : panneau acrylique, compositeur et navigation."""
    from src.ui.stylesheet import qss_scrollbar

    size_md = int(t.SIZE_MD.rstrip("px")) + font_offset
    size_lg = int(t.SIZE_LG.rstrip("px")) + font_offset
    size_sm = int(t.SIZE_SM.rstrip("px")) + font_offset
    nav_size = 13 + font_offset
    return (
        f"""
        QDialog {{ background: transparent; }}
        QToolTip {{
            background-color: {t.COLOR_BG_SURFACE};
            color: {t.COLOR_TEXT_PRIMARY};
            border: 1px solid {t.COLOR_BORDER};
            border-radius: {t.RADIUS_SM};
            padding: 5px 8px;
            font-family: {t.FONT_TEXT};
            font-size: {size_md}px;
        }}
        QFrame#DocPanel {{
            background-color: {t.COLOR_BG_ACRYLIC};
            border: 1px solid {t.COLOR_BORDER_ACRYLIC};
            border-radius: {t.RADIUS_2XL};
        }}
        QFrame#DocHeader {{ background: transparent; border: none; }}
        QLabel {{
            background: transparent; color: {t.COLOR_TEXT_PRIMARY}; border: none;
            font-family: {t.FONT_TEXT}; font-size: {size_md}px;
        }}
        QLabel#DocTitle {{
            font-family: {t.FONT_DISPLAY};
            font-size: {size_lg}px; font-weight: 700; color: {t.COLOR_TEXT_PRIMARY};
        }}
        QFrame#Composer {{
            background: {t.COLOR_COMPOSER_BACKGROUND};
            border: 1px solid {t.COLOR_BORDER_INPUT};
            border-radius: {t.RADIUS_XL};
        }}
        QFrame#DocumentCard {{
            background: transparent;
            border: none;
            border-radius: 0;
        }}
        QLabel#Preview {{
            background: {t.COLOR_PREVIEW_BACKGROUND};
            border: 1px solid {t.COLOR_BORDER_SUBTLE};
            border-radius: {t.RADIUS_MD}; padding: 3px;
        }}
        QTextEdit {{
            background: transparent; border: none; padding: 6px 1px 4px 1px;
            color: {t.COLOR_TEXT_PRIMARY}; font-family: {t.FONT_TEXT}; font-size: {size_md}px;
        }}
        QTextBrowser#Response {{
            background: transparent; border: none; padding: 0;
            font-family: {t.FONT_TEXT}; font-size: {size_md}px;
        }}
        QPushButton#HeaderIconButton, QPushButton#ActionIconButton {{
            background: transparent; border: none; border-radius: {t.RADIUS_XL}; padding: 0; margin: 0;
        }}
        QPushButton#HeaderIconButton:hover, QPushButton#ActionIconButton:hover,
        QPushButton#HeaderIconButton:pressed, QPushButton#ActionIconButton:pressed {{
            background: {t.COLOR_HOVER_DARK}; border: none;
        }}
        QPushButton#HeaderIconButton:focus, QPushButton#ActionIconButton:focus {{
            background: {t.COLOR_HOVER_DARK}; border: none; /* Focus ring intentionally disabled; token retained for documentation: {t.COLOR_PRIMARY} */
        }}
        QPushButton#HeaderIconButton:disabled, QPushButton#ActionIconButton:disabled {{
            background: transparent;
        }}
        QPushButton#MicRecording {{
            background: {t.COLOR_RECORDING_BACKGROUND}; border: none; border-radius: {t.RADIUS_XL};
        }}
        """
        + qss_scrollbar()
        + f"""
        QLabel#DocStatus {{
            color: {t.COLOR_PRIMARY}; font-family: {t.FONT_TEXT};
            font-size: {size_sm}px; font-style: italic; padding: 2px 4px;
        }}
        QFrame#TurnNavigation {{
            background: transparent; border: none; border-radius: 7px;
        }}
        QFrame#TurnNavigation:hover {{
            background: {t.COLOR_NAVIGATION_HOVER};
        }}
        QFrame#TurnNavigation QPushButton {{
            color: {t.COLOR_TEXT_MUTED}; background: transparent; border: none;
            font-size: {nav_size}px; padding: 0;
        }}
        QFrame#TurnNavigation QPushButton:hover,
        QFrame#TurnNavigation QPushButton:checked {{
            color: {t.COLOR_PRIMARY};
        }}
        """
    )


def qss_document_preview_dialog() -> str:
    """Dialogue d'agrandissement d'une capture ou d'une page."""
    return (
        f"QDialog{{background:{t.COLOR_BG_PAGE};}}"
        f"QScrollArea{{background:{t.COLOR_BG_PAGE};border:none;}}"
        f"QLabel{{background:{t.COLOR_BG_SURFACE};border:none;}}"
    )


def qss_tool_call_step() -> str:
    """Ligne de timeline d'outil et état hover."""
    return f"""
        QFrame#ToolCallStepRow {{
            background: transparent;
            border: none;
            border-radius: {t.RADIUS_MD};
            padding: 0px;
            margin: 0px;
        }}
        QFrame#ToolCallStepRow:hover {{
            background: {t.COLOR_OVERLAY_HOVER};
        }}
    """


def qss_tool_code_browser(is_error: bool = False) -> str:
    """Bloc de sortie outil, avec variante d'erreur."""
    text_color = t.COLOR_DANGER if is_error else t.COLOR_TOOL_TEXT
    return f"""
        QTextBrowser {{
            background-color: {t.COLOR_TOOL_CODE_BACKGROUND};
            color: {text_color};
            border: 1px solid {t.COLOR_TOOL_CODE_BORDER};
            border-radius: {t.RADIUS_SM};
            font-family: 'Consolas', 'Cascadia Code', monospace;
            font-size: {t.SIZE_SM};
            padding: 4px 6px;
        }}
    """

