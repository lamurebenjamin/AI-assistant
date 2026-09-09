"""Bulles de dialogue (utilisateur / assistant) et navigateur de texte avec loupe intégrée."""

from PyQt5.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import QFrame, QTextBrowser, QVBoxLayout

from src.ui.design_tokens import (
    COLOR_PRIMARY_BORDER,
    COLOR_PRIMARY_LIGHT,
    COLOR_SUCCESS_BORDER,
    COLOR_SUCCESS_LIGHT,
    COLOR_SUCCESS_TEXT,
    COLOR_USER_TEXT,
    FONT_TEXT,
    RADIUS_XL,
    SIZE_MD,
)


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

    link_clicked = pyqtSignal(object)

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.setObjectName("UserBubble" if role == "user" else "AssistantBubble")
        self.setSizePolicy(self.sizePolicy().Preferred, self.sizePolicy().Fixed)
        self.setMaximumWidth(10_000)
        self.setStyleSheet(
            f"QFrame#UserBubble {{ background:{COLOR_PRIMARY_LIGHT}; border:1px solid {COLOR_PRIMARY_BORDER}; "
            f"border-radius:{RADIUS_XL}; }}"
            f"QFrame#AssistantBubble {{ background:{COLOR_SUCCESS_LIGHT}; border:1px solid {COLOR_SUCCESS_BORDER}; "
            f"border-radius:{RADIUS_XL}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)
        self.browser = SourceZoomTextBrowser(self)
        self.browser.setReadOnly(True)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setFrameShape(QFrame.NoFrame)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setSizePolicy(
            self.browser.sizePolicy().Expanding,
            self.browser.sizePolicy().Fixed,
        )
        text_color = COLOR_USER_TEXT if role == "user" else COLOR_SUCCESS_TEXT
        self.browser.setStyleSheet(
            f"QTextBrowser {{ background:transparent; border:none; padding:0; "
            f"color:{text_color}; font-family:{FONT_TEXT}; font-size:{SIZE_MD}; }}"
        )
        self.browser.document().setDocumentMargin(0)
        self.browser.anchorClicked.connect(self.link_clicked.emit)
        layout.addWidget(self.browser)

    def set_html(self, value: str) -> None:
        self.browser.setHtml(value or "")
        self._fit_height()

    def _fit_height(self) -> None:
        # La largeur de texte est explicitement limitée au viewport. Cela force
        # le retour à la ligne et empêche tout contenu de dépasser à droite.
        viewport_width = max(40, self.browser.viewport().width())
        self.browser.document().setTextWidth(viewport_width)
        height = max(20, int(self.browser.document().size().height()) + 2)
        self.browser.setFixedHeight(height)
        self.setFixedHeight(height + 20)

    def fit_to_content_width(self, maximum_width: int, minimum_width: int = 54) -> None:
        """Adapte la bulle au contenu sans dépasser la largeur disponible."""
        maximum_width = max(minimum_width, int(maximum_width))
        self.browser.document().setTextWidth(-1)
        ideal_width = int(self.browser.document().idealWidth() + 0.999)
        margins = self.layout().contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        target_width = max(
            minimum_width,
            min(maximum_width, ideal_width + horizontal_padding + 2),
        )
        self.setFixedWidth(target_width)
        self.browser.setFixedWidth(max(30, target_width - horizontal_padding))
        self._fit_height()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_height)
