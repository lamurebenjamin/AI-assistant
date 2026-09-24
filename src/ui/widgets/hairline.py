"""Séparateur 1px partagé sous les barres de titre."""

from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import HorizontalSeparator

import src.ui.design_tokens as t


class HairlineSeparator(QWidget):
    """Ligne horizontale inset utilisant HorizontalSeparator de QFluentWidgets."""

    def __init__(self, parent=None, inset: int | None = None):
        super().__init__(parent)
        self._inset = t.SEPARATOR_INSET if inset is None else inset
        layout = QHBoxLayout(self)
        layout.setContentsMargins(self._inset, 0, self._inset, 0)
        layout.setSpacing(0)
        self.line = HorizontalSeparator(self)
        layout.addWidget(self.line)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.line.setStyleSheet(
            f"background: {t.COLOR_SEPARATOR}; border: none;"
        )
