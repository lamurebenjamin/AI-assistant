"""Libellés de statut sémantiques (succès, erreur, attente)."""

from PySide6.QtWidgets import QLabel

import src.ui.design_tokens as t


class StatusLabel(QLabel):
    """QLabel dont la couleur suit un ton sémantique du thème actif."""

    def __init__(self, text="", parent=None, tone: str = "muted", weight: int = 600):
        super().__init__(text, parent)
        self._tone = tone
        self._weight = weight
        self._italic = False
        self._size = None
        self.refresh_theme()

    def set_tone(self, tone: str, weight: int | None = None) -> None:
        self._tone = tone
        if weight is not None:
            self._weight = weight
        self.refresh_theme()

    def set_hint_style(self) -> None:
        self._tone = "muted"
        self._italic = True
        self._size = t.SIZE_SM
        self._weight = 400
        self.refresh_theme()

    def refresh_theme(self) -> None:
        colors = {
            "title": t.COLOR_TEXT_PRIMARY,
            "success": t.COLOR_SUCCESS_STRONG,
            "danger": t.COLOR_DANGER,
            "warning": t.COLOR_WARNING,
            "info": t.COLOR_PRIMARY,
            "loading": t.COLOR_PRIMARY,
            "muted": t.COLOR_TEXT_SECONDARY,
        }
        color = colors.get(self._tone, t.COLOR_TEXT_SECONDARY)
        size = self._size or t.SIZE_MD
        italic = "italic" if self._italic else "normal"
        self.setStyleSheet(
            f"color: {color}; font-weight: {self._weight}; "
            f"font-size: {size}; font-style: {italic}; background: transparent;"
        )
