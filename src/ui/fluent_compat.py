"""Adaptateurs et exports QFluentWidgets pour intégration fluide avec l'existant.

Certains widgets natifs de QFluentWidgets (comme LineEdit, TextEdit, PlainTextEdit)
ont une signature __init__(self, parent=None) différente de PySide6 qui accepte
(self, text, parent=None). Ces adaptateurs garantissent une compatibilité 100%
sans casser le code existant tout en offrant le rendu Windows 11 natif.
"""

from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    Action,
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    HorizontalSeparator,
    ListWidget,
    OpacityAniStackedWidget,
    Pivot,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    RoundMenu,
    SmoothScrollArea,
    SpinBox,
    SubtitleLabel,
    SwitchButton,
    SystemThemeListener,
    Theme,
    TitleLabel,
    ToolTipFilter,
    setTheme,
    setThemeColor,
)
from qfluentwidgets import (
    LineEdit as _QFLine,
)
from qfluentwidgets import (
    PlainTextEdit as _QFPlain,
)
from qfluentwidgets import (
    TextEdit as _QFText,
)


class LineEdit(_QFLine):
    """LineEdit Fluent compatible avec les signatures (text, parent) et (parent)."""

    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            text = args[0]
            parent = args[1] if len(args) > 1 else kwargs.pop("parent", None)
            super().__init__(parent=parent, **kwargs)
            self.setText(text)
        else:
            super().__init__(*args, **kwargs)


class TextEdit(_QFText):
    """TextEdit Fluent compatible avec les signatures (text, parent) et (parent)."""

    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            text = args[0]
            parent = args[1] if len(args) > 1 else kwargs.pop("parent", None)
            super().__init__(parent=parent, **kwargs)
            self.setPlainText(text)
        else:
            super().__init__(*args, **kwargs)


class PlainTextEdit(_QFPlain):
    """PlainTextEdit Fluent compatible avec les signatures (text, parent) et (parent)."""

    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            text = args[0]
            parent = args[1] if len(args) > 1 else kwargs.pop("parent", None)
            super().__init__(parent=parent, **kwargs)
            self.setPlainText(text)
        else:
            super().__init__(*args, **kwargs)


def install_tooltip(widget: QWidget, text: str, delay: int = 300) -> None:
    """Source unique pour les tooltips dans toute l'application.

    Assigne le texte via setToolTip() et installe QFluentWidgets ToolTipFilter
    pour un rendu Fluent cohérent sur tous les widgets, quel que soit leur type.
    Évite de double-installer le filtre si appelé plusieurs fois.

    Args:
        widget: Le widget Qt qui recevra le tooltip.
        text:   Le texte à afficher.
        delay:  Délai avant affichage en millisecondes (défaut 300 ms).
    """
    widget.setToolTip(text)
    # Ne pas installer un second filtre si on réappelle la fonction
    for f in widget.children():
        if isinstance(f, ToolTipFilter):
            return
    widget.installEventFilter(ToolTipFilter(widget, showDelay=delay))


__all__ = [
    "Action",
    "BodyLabel",
    "CaptionLabel",
    "CheckBox",
    "ComboBox",
    "HorizontalSeparator",
    "LineEdit",
    "ListWidget",
    "OpacityAniStackedWidget",
    "Pivot",
    "PlainTextEdit",
    "PrimaryPushButton",
    "ProgressBar",
    "PushButton",
    "RoundMenu",
    "SmoothScrollArea",
    "SpinBox",
    "SubtitleLabel",
    "SwitchButton",
    "SystemThemeListener",
    "TextEdit",
    "Theme",
    "TitleLabel",
    "ToolTipFilter",
    "install_tooltip",
    "setTheme",
    "setThemeColor",
]
