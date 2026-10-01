"""Styles QSS tools ; tokens lus au moment de chaque appel."""

import src.ui.design_tokens as t


def qss_tool_group_header(muted_color: str | None = None) -> str:
    """En-tête de groupe d'exécution d'outil."""
    color = muted_color or t.COLOR_TEXT_MUTED
    return f"""
        font-family: {t.FONT_TEXT};
        font-size: {t.SIZE_SM};
        font-weight: 500;
        color: {color};
        background: transparent;
    """

def qss_tool_steps_container() -> str:
    """Conteneur des étapes d'outil avec ligne verticale."""
    return f"background: transparent; border-left: 1px solid {t.COLOR_BORDER};"

def qss_thinking_details(font_size: int = 13) -> str:
    """Détails de pensée (thinking process) dépliables."""
    return (
        f"background: transparent; border-left: 1px solid {t.COLOR_BORDER}; "
        "margin-left: 7px; "
        f"padding: 0 8px 2px 10px; font-family: {t.FONT_TEXT}; "
        f"font-size: {font_size}px; font-style: italic; "
        f"color: {t.COLOR_TEXT_SECONDARY};"
    )

def qss_skill_tag_title(
    color: str = "", font_size: int = 11, weight: int = 600
) -> str:
    """Libellé de badge de skill actif."""
    text_color = color or t.COLOR_TEXT_PRIMARY
    return (
        f"color: {text_color}; font-family: {t.FONT_TEXT}; "
        f"font-size: {font_size}px; font-weight: {weight}; background: transparent;"
    )

def qss_skill_tag_frame() -> str:
    """Contour de badge de skill avec fond teinté."""
    return (
        f"QFrame#SkillTag {{ background: {t.COLOR_PRIMARY_LIGHT}; "
        f"border: 1px solid {t.COLOR_PRIMARY_BORDER}; "
        f"border-radius: {t.RADIUS_MD}; }}"
    )

def qss_timeline_connector() -> str:
    """Ligne de connexion verticale pour la timeline d'étapes."""
    return f"color: {t.COLOR_BORDER}; background: {t.COLOR_BORDER};"

def qss_timeline_header_title(color: str) -> str:
    """Titre d'un en-tête d'étape ou de groupe de pensée."""
    return (
        f"font-family: {t.FONT_TEXT}; font-size: {t.SIZE_SM}; "
        f"font-weight: 500; color: {color}; background: transparent;"
    )

def qss_status_label(
    color: str, size: str, weight: int = 500, italic: bool = False
) -> str:
    """Style d'étiquette de statut avec ton et graisse dynamiques."""
    font_style = "italic" if italic else "normal"
    return (
        f"color: {color}; font-weight: {weight}; "
        f"font-size: {size}; font-style: {font_style}; background: transparent;"
    )

def qss_shimmer_status_label(font_offset: int = 0) -> str:
    """Style du libellé animé scintillant de progression."""
    size = int(t.SIZE_SM.rstrip("px")) + font_offset
    return f"font-family: {t.FONT_TEXT}; font-size: {size}px; background: transparent;"
