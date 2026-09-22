"""Tag de compétence partagé (bulles et compositeur)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

import src.ui.design_tokens as t
from src.ui.icons import get_application_icon, get_default_tool_icon


class SkillTag(QFrame):
    """Icône + titre d'une skill, stylés par tokens."""

    def __init__(
        self,
        parent=None,
        *,
        font_size_offset: int = 0,
        framed: bool = False,
        text_color: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("SkillTag")
        self._font_size_offset = font_size_offset
        self._framed = framed
        self._text_color = text_color
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 8, 3) if framed else layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(t.ICON_SIZE_SKILL, t.ICON_SIZE_SKILL)
        self.icon_label.setScaledContents(framed)
        self.title_label = QLabel(self)
        self.title_label.setWordWrap(False)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.title_label, 0, Qt.AlignVCenter)
        if not framed:
            layout.addStretch(1)
        self.refresh_theme()
        self.hide()

    def refresh_theme(self) -> None:
        color = self._text_color or t.COLOR_TEXT_PRIMARY
        size = int(t.SIZE_SM.rstrip("px")) + self._font_size_offset
        self.title_label.setStyleSheet(
            f"color:{color}; font-family:{t.FONT_TEXT}; font-size:{size}px; "
            "font-weight:600; background:transparent;"
        )
        if self._framed:
            self.setStyleSheet(
                f"QFrame#SkillTag {{ background:{t.COLOR_PRIMARY_LIGHT}; "
                f"border:1px solid {t.COLOR_PRIMARY_BORDER}; "
                f"border-radius:{t.RADIUS_MD}; }}"
            )

    def set_tag(self, tag: dict | None) -> None:
        if not tag:
            self.hide()
            return
        icon_path = tag.get("icon")
        icon = get_application_icon(icon_path) if icon_path else get_default_tool_icon()
        pixmap = icon.pixmap(32, 32, QIcon.Normal, QIcon.On)
        if pixmap.isNull():
            self.hide()
            return
        self.icon_label.setPixmap(
            pixmap.scaled(
                t.ICON_SIZE_SKILL,
                t.ICON_SIZE_SKILL,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.title_label.setText(str(tag.get("title", "")))
        self.show()
