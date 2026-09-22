"""Bulles de dialogue (utilisateur / assistant) et navigateur de texte avec loupe intégrée."""

import math
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
)
from shiboken6 import isValid as is_qt_object_valid

import src.ui.design_tokens as t
from src.ui.widgets.skill_tag import SkillTag



class SourceZoomTextBrowser(QTextBrowser):
    """QTextBrowser affichant une loupe centrée sous la souris sur les captures."""

    ZOOM_SIZE = 190
    ZOOM_FACTOR = 2.2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._zoom_pixmap = None
        self._zoom_center = None
        self._zoom_position = None

    def leaveEvent(self, event):
        self._clear_zoom()
        super().leaveEvent(event)

    def _clear_zoom(self):
        if self._zoom_pixmap is not None:
            self._zoom_pixmap = None
            self._zoom_center = None
            self._zoom_position = None
            self.viewport().update()

    def mouseMoveEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        image_format = cursor.charFormat().toImageFormat()
        if not image_format.isValid() or not image_format.name():
            self._clear_zoom()
            super().mouseMoveEvent(event)
            return

        pixmap = QPixmap(image_format.name())
        if pixmap.isNull():
            self._clear_zoom()
            super().mouseMoveEvent(event)
            return

        block = cursor.block()
        layout = block.layout()
        line = layout.lineForTextPosition(cursor.positionInBlock())
        block_rect = self.document().documentLayout().blockBoundingRect(block)
        x = block_rect.x() + line.cursorToX(cursor.positionInBlock())
        y = block_rect.y() + line.y()
        width = (
            image_format.width() if image_format.width() > 0 else pixmap.width()
        )
        height = (
            image_format.height()
            if image_format.height() > 0
            else pixmap.height()
        )
        image_rect = QRectF(
            x - self.horizontalScrollBar().value(),
            y - self.verticalScrollBar().value(),
            width,
            height,
        )

        if not image_rect.contains(event.pos()):
            self._clear_zoom()
            super().mouseMoveEvent(event)
            return

        relative_x = max(
            0.0,
            min(
                1.0,
                (event.x() - image_rect.left()) / max(1.0, image_rect.width()),
            ),
        )
        relative_y = max(
            0.0,
            min(
                1.0,
                (event.y() - image_rect.top()) / max(1.0, image_rect.height()),
            ),
        )
        self._zoom_pixmap = pixmap
        self._zoom_center = (
            relative_x * pixmap.width(),
            relative_y * pixmap.height(),
        )
        self._zoom_position = event.pos()
        self.viewport().update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if (
            self._zoom_pixmap is None
            or self._zoom_center is None
            or self._zoom_position is None
        ):
            return

        source_size = self.ZOOM_SIZE / self.ZOOM_FACTOR
        center_x, center_y = self._zoom_center
        source_rect = QRectF(
            center_x - source_size / 2,
            center_y - source_size / 2,
            source_size,
            source_size,
        )
        source_rect.moveLeft(
            max(
                0.0,
                min(
                    source_rect.left(),
                    self._zoom_pixmap.width() - source_size,
                ),
            )
        )
        source_rect.moveTop(
            max(
                0.0,
                min(
                    source_rect.top(),
                    self._zoom_pixmap.height() - source_size,
                ),
            )
        )

        x = self._zoom_position.x() + 18
        y = self._zoom_position.y() + 18
        if x + self.ZOOM_SIZE > self.viewport().width() - 8:
            x = self._zoom_position.x() - self.ZOOM_SIZE - 18
        if y + self.ZOOM_SIZE > self.viewport().height() - 8:
            y = self._zoom_position.y() - self.ZOOM_SIZE - 18
        target = QRectF(max(8, x), max(8, y), self.ZOOM_SIZE, self.ZOOM_SIZE)

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(target, 14, 14)
        painter.setClipPath(path)
        painter.drawPixmap(target, self._zoom_pixmap, source_rect)
        painter.setClipping(False)
        painter.setPen(QColor(123, 157, 190))
        painter.drawRoundedRect(target, 14, 14)
        painter.end()


class ChatBubble(QFrame):
    """Bulle de conversation réelle, avec coins arrondis et largeur contrainte."""

    link_clicked = Signal(object)

    def __init__(self, role: str, parent=None, font_size_offset: int = 0):
        super().__init__(parent)
        self.role = role
        self.font_size_offset = font_size_offset
        self.setObjectName(
            "UserBubble" if role == "user"
            else "ErrorBubble" if role == "error"
            else "AssistantBubble"
        )
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMaximumWidth(10_000)
        if role == "user":
            layout = QVBoxLayout(self)
            layout.setContentsMargins(
                t.CHAT_BUBBLE_PADDING_X,
                t.CHAT_BUBBLE_PADDING_Y,
                t.CHAT_BUBBLE_PADDING_X,
                4,
            )
        elif role == "error":
            layout = QVBoxLayout(self)
            layout.setContentsMargins(
                t.CHAT_BUBBLE_PADDING_X,
                t.CHAT_BUBBLE_PADDING_Y,
                t.CHAT_BUBBLE_PADDING_X,
                t.CHAT_BUBBLE_PADDING_Y,
            )
        else:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        self.skill_tag_row = SkillTag(
            self,
            font_size_offset=font_size_offset,
            framed=False,
            text_color=(
                t.COLOR_USER_TEXT if role == "user" else t.COLOR_TEXT_PRIMARY
            ),
        )
        self.skill_tag_icon = self.skill_tag_row.icon_label
        self.skill_tag_title = self.skill_tag_row.title_label
        self.browser = SourceZoomTextBrowser(self)
        self.browser.setReadOnly(True)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setFrameShape(QFrame.NoFrame)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        font = self.browser.font()
        font.setFamily("-apple-system")
        font.setStyleHint(QFont.SansSerif)
        pixel_size = int(t.SIZE_MD.rstrip("px")) + font_size_offset
        font.setPixelSize(pixel_size)
        self.browser.setFont(font)
        self.browser.document().setDefaultFont(font)
        if role == "user":
            self.browser.setAlignment(Qt.AlignLeft)
        self.browser.document().setDocumentMargin(0)
        self.browser.anchorClicked.connect(self.link_clicked.emit)
        self.content_layout = QHBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_layout.addWidget(self.skill_tag_row, 0, Qt.AlignTop)
        self.content_layout.addWidget(self.browser, 1)
        layout.addLayout(self.content_layout)
        self.timestamp_label = None
        self.refresh_theme()

    def refresh_theme(self) -> None:
        if self.role == "user":
            self.setStyleSheet(
                f"QFrame#UserBubble {{ background:{t.COLOR_BG_SUBTLE}; border:none; "
                f"border-radius:{t.RADIUS_XL}; }}"
            )
        elif self.role == "error":
            self.setStyleSheet(
                f"QFrame#ErrorBubble {{ background:{t.COLOR_ERROR_BACKGROUND}; "
                f"border:1px solid {t.COLOR_ERROR_BORDER}; border-radius:{t.RADIUS_MD}; }}"
            )
        else:
            self.setStyleSheet(
                "QFrame#AssistantBubble { background: transparent; border: none; border-radius: 0; }"
            )
        text_color = (
            t.COLOR_USER_TEXT if self.role == "user"
            else t.COLOR_DANGER if self.role == "error"
            else t.COLOR_TEXT_PRIMARY
        )
        self.browser.setStyleSheet(
            f"QTextBrowser {{ background:transparent; border:none; padding:0; "
            f"color:{text_color}; font-family:{t.FONT_TEXT}; "
            f"font-size:{int(t.SIZE_MD.rstrip('px')) + self.font_size_offset}px; }}"
        )
        self.skill_tag_row._text_color = (
            t.COLOR_USER_TEXT if self.role == "user" else t.COLOR_TEXT_PRIMARY
        )
        self.skill_tag_row.refresh_theme()

    def set_skill_tag(self, tag: dict) -> None:
        """Affiche le tag avec une image Qt haute résolution, hors HTML."""
        self.skill_tag_row.set_tag(tag)

    def set_html(self, value: str) -> None:
        content = value or ""
        self.browser.setHtml(content)
        self._fit_height()

    def set_timestamp(self, timestamp: str) -> None:
        return

    def _fit_height(self) -> None:
        if not is_qt_object_valid(self):
            return
        margins = self.layout().contentsMargins() if self.layout() else None
        h_margins = (margins.left() + margins.right()) if margins else 4
        v_margins = (margins.top() + margins.bottom()) if margins else 4
        tag_w = (self.skill_tag_row.sizeHint().width() + 5) if self.skill_tag_row.isVisible() else 0

        if self.width() > 40:
            target_text_w = max(40, self.width() - h_margins - tag_w)
        elif self.browser.viewport().width() > 100:
            target_text_w = max(40, self.browser.viewport().width() - tag_w)
        else:
            parent_w = self.parentWidget().width() if self.parentWidget() else 350
            target_text_w = max(40, parent_w - h_margins - tag_w)

        self.browser.document().setTextWidth(target_text_w)
        doc_h = math.ceil(self.browser.document().size().height())
        height = max(20, doc_h + 4)
        self.browser.setFixedHeight(height)
        tag_height = self.skill_tag_row.sizeHint().height() if self.skill_tag_row.isVisible() else 0
        self.setFixedHeight(max(height, tag_height) + v_margins + 2)

    def fit_to_content_width(self, maximum_width: int, minimum_width: int = 0) -> None:
        """Adapte la bulle au contenu sans dépasser la largeur disponible."""
        maximum_width = max(minimum_width, int(maximum_width))
        document = self.browser.document()
        document.setTextWidth(-1)
        document.adjustSize()
        natural_width = max(
            document.idealWidth(),
            document.size().width(),
        )
        margins = self.layout().contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        plain_text = self.browser.toPlainText()
        if self.role == "user" and "\n" not in plain_text:
            natural_width = max(
                natural_width,
                QFontMetrics(self.browser.font()).horizontalAdvance(plain_text),
            )
        target_width = max(
            min(minimum_width, maximum_width),
            min(maximum_width, math.ceil(natural_width) + horizontal_padding + 2),
        )
        if self.skill_tag_row.isVisible():
            tag_width = self.skill_tag_row.sizeHint().width() + 8
            target_width = max(target_width, min(maximum_width, max(280, tag_width + 160)))
        self.setFixedWidth(target_width)
        content_width = max(1, target_width - horizontal_padding)
        if self.skill_tag_row.isVisible():
            tag_width = min(
                self.skill_tag_row.sizeHint().width(),
                max(20, content_width - 40),
            )
            self.skill_tag_row.setFixedWidth(tag_width)
            self.skill_tag_title.setMaximumWidth(
                max(20, tag_width - self.skill_tag_icon.width() - 5)
            )
            self.browser.setFixedWidth(
                max(30, content_width - tag_width - self.content_layout.spacing())
            )
        else:
            self.browser.setFixedWidth(content_width)
        self.setMaximumWidth(maximum_width)
        document.setTextWidth(content_width)
        self._fit_height()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_height)
