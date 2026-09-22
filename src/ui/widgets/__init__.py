# -*- coding: utf-8 -*-
"""Widgets UI réutilisables."""

from src.ui.widgets.animated_buttons import AnimatedComposerButton, AnimatedHeaderButton
from src.ui.widgets.audio_bars import LiveAudioIndicator, ScrollingAudioBars
from src.ui.widgets.chat_bubble import ChatBubble
from src.ui.widgets.composer_bar import ComposerBar
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.skill_tag import SkillTag
from src.ui.widgets.status_label import StatusLabel
from src.ui.widgets.window_chrome import WindowChrome

__all__ = [
    "AnimatedComposerButton",
    "AnimatedHeaderButton",
    "ChatBubble",
    "ComposerBar",
    "HairlineSeparator",
    "LiveAudioIndicator",
    "ScrollingAudioBars",
    "SkillTag",
    "StatusLabel",
    "WindowChrome",
]
