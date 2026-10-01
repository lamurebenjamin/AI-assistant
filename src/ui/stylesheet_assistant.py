"""Styles QSS assistant ; tokens lus au moment de chaque appel."""

import src.ui.design_tokens as t
from src.ui.stylesheet_builders import build_acrylic_window_qss


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

def qss_voice_recording_indicator() -> str:
    """Style complet de l'indicateur de saisie vocale."""
    return (
        build_acrylic_window_qss()
        + f"""
        QLabel#VoiceText, QLabel#VoiceClock {{
            background: transparent;
            color: {t.COLOR_TEXT_PRIMARY};
            border: none;
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_LG};
        }}
        QLabel#VoiceClock {{ color: {t.COLOR_TEXT_MUTED}; }}
        """
    )
