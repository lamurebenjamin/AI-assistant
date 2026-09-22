"""Barre de titre partagée : logo, titre, actions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

import src.ui.design_tokens as t
from src.config.schema import APP_DIR
from src.ui.icons import get_logo_pixmap


class WindowChrome(QFrame):
    """Chrome d'en-tête unique pour toutes les fenêtres flottantes."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        object_name: str = "Header",
        title_object_name: str = "TitleLabel",
        centered: bool = False,
        app_dir: str = "",
    ):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFixedHeight(t.HEADER_HEIGHT)
        right = (
            t.HEADER_MARGIN_RIGHT_CENTERED if centered else t.HEADER_MARGIN_RIGHT
        )
        spacing = t.HEADER_SPACING_CENTERED if centered else t.HEADER_SPACING
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            t.HEADER_MARGIN_LEFT,
            t.HEADER_MARGIN_TOP,
            right,
            0,
        )
        layout.setSpacing(spacing)
        layout.setAlignment(Qt.AlignVCenter)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(t.ICON_SIZE_HEADER, t.ICON_SIZE_HEADER)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(
            get_logo_pixmap(t.ICON_SIZE_HEADER, app_dir or APP_DIR)
        )
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName(title_object_name)
        self.title_label.setTextFormat(Qt.PlainText)
        if centered:
            self.title_label.setAlignment(Qt.AlignCenter)
        else:
            self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.title_label, 1)

        if centered:
            self._balance = QWidget(self)
            self._balance.setFixedSize(t.ICON_SIZE_HEADER, t.ICON_SIZE_HEADER)
            layout.addWidget(self._balance)
        else:
            self._balance = None

        self._layout = layout

    def add_action(self, widget: QWidget) -> None:
        """Ajoute un contrôle à droite du titre (avant l'espaceur centré)."""
        if self._balance is not None:
            self._layout.insertWidget(self._layout.indexOf(self._balance), widget)
        else:
            self._layout.addWidget(widget, 0, Qt.AlignVCenter)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def refresh_logo(self, app_dir: str = "") -> None:
        self.icon_label.setPixmap(
            get_logo_pixmap(t.ICON_SIZE_HEADER, app_dir or APP_DIR)
        )
