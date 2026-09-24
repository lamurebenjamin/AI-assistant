"""Reusable attachment preview and PDF page-range controller."""

import os
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SmoothScrollArea

import src.ui.design_tokens as t
from src.config.schema import LOGGER
from src.ui.stylesheet import (
    qss_document_attachment_scroll,
    qss_document_page_dash,
    qss_document_page_editor,
    qss_document_page_name,
)
from src.ui.widgets.attachment_widget import AttachmentPreviewWidget

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None


class DocumentAttachmentPreview:
    """Owns attachment cards, PDF thumbnails, and page-range selections."""

    CELL_SIZE = (104, 110)

    def __init__(self, parent, font_size_offset=0, update_height=None, fallback_pixmap=None):
        self.font_size_offset = font_size_offset
        self._update_height = update_height or (lambda: None)
        self._fallback_pixmap = fallback_pixmap
        self.paths = []
        self.page_selections = {}

        self.document_area = QFrame(parent)
        self.document_area.setObjectName("DocumentCard")
        area_layout = QVBoxLayout(self.document_area)
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(0)
        self.image_scroll = SmoothScrollArea(self.document_area)
        self.image_scroll.setWidgetResizable(False)
        self.image_scroll.setFrameShape(QFrame.NoFrame)
        self.image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.image_scroll.setFixedHeight(t.DOCUMENT_PREVIEW_HEIGHT)
        self.image_scroll.setStyleSheet(qss_document_attachment_scroll())
        self.image_strip = QWidget()
        self.image_strip.setFixedHeight(116)
        self.image_strip_layout = QHBoxLayout(self.image_strip)
        self.image_strip_layout.setContentsMargins(6, 6, 6, 2)
        self.image_strip_layout.setSpacing(10)
        self.image_strip_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.image_scroll.setWidget(self.image_strip)
        area_layout.addWidget(self.image_scroll)
        self.document_area.hide()

    @staticmethod
    def page_count(path):
        if path.lower().endswith(".pdf") and fitz is not None:
            doc = fitz.open(path)
            try:
                return max(1, doc.page_count)
            finally:
                doc.close()
        return 1

    def add_paths(self, paths, supported):
        for path in paths:
            path = os.path.abspath(path)
            if supported(path) and path not in self.paths:
                count = self.page_count(path)
                self.paths.append(path)
                self.page_selections[path] = (1, count)
        if self.paths:
            self.show_document(len(self.paths) - 1)

    def clear_image_strip(self):
        while self.image_strip_layout.count():
            widget = self.image_strip_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()

    def remove_path(self, path):
        if path in self.paths:
            self.paths.remove(path)
            self.page_selections.pop(path, None)
        self.show_document(len(self.paths) - 1)

    def rebuild_image_strip(self):
        self.clear_image_strip()
        cell_w, cell_h = self.CELL_SIZE
        preview_w, pdf_preview_h = 86, 66
        for path in self.paths:
            is_pdf = path.lower().endswith(".pdf")
            holder = AttachmentPreviewWidget(self.image_strip)
            holder.setFixedSize(cell_w, cell_h)
            if is_pdf:
                count = self.page_count(path)
                first, last = self.page_selections.get(path, (1, count))
                source = QPixmap()
                if fitz is not None:
                    try:
                        doc = fitz.open(path)
                        try:
                            page_idx = max(0, min(first - 1, doc.page_count - 1))
                            pix = doc.load_page(page_idx).get_pixmap(
                                matrix=fitz.Matrix(1.4, 1.4), alpha=False
                            )
                            source.loadFromData(pix.tobytes("png"))
                        finally:
                            doc.close()
                    except Exception:  # noqa: BLE001
                        LOGGER.exception("Impossible de générer la vignette PDF pour %s", path)
                if source.isNull() and self._fallback_pixmap:
                    source = self._fallback_pixmap(preview_w, pdf_preview_h - 6)
                shown = source.scaled(
                    preview_w, pdf_preview_h - 6, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                x = (cell_w - shown.width()) // 2
                y = 4 + max(0, (pdf_preview_h - 6 - shown.height()) // 2)
                rounded = QPixmap(shown.size())
                rounded.fill(Qt.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.Antialiasing, True)
                rect = QRectF(0.5, 0.5, shown.width() - 1.0, shown.height() - 1.0)
                clip = QPainterPath()
                clip.addRoundedRect(rect, 5.0, 5.0)
                painter.setClipPath(clip)
                painter.drawPixmap(0, 0, shown)
                painter.setPen(QPen(QColor(0, 0, 0, 32), 1.0))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect, 5.0, 5.0)
                painter.end()
                label = QLabel(holder)
                label.setPixmap(rounded)
                label.setGeometry(x, y, shown.width(), shown.height())

                pdf_name = Path(path).stem
                displayed_name = pdf_name if len(pdf_name) <= 12 else pdf_name[:12] + "..."
                name_label = QLabel(displayed_name, holder)
                name_label.setGeometry(4, 68, cell_w - 8, 15)
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setToolTip(pdf_name)
                name_label.setStyleSheet(qss_document_page_name(self.font_size_offset))

                pages = QWidget(holder)
                pages.setGeometry(0, 82, cell_w, 25)
                row = QHBoxLayout(pages)
                row.setContentsMargins(15, 0, 15, 1)
                row.setSpacing(0)
                first_edit, last_edit = QLineEdit(str(first)), QLineEdit(str(last))
                for edit in (first_edit, last_edit):
                    edit.setAlignment(Qt.AlignCenter)
                    edit.setFixedSize(24, 19)
                    edit.setStyleSheet(qss_document_page_editor(self.font_size_offset))
                dash = QLabel("-")
                dash.setAlignment(Qt.AlignCenter)
                dash.setFixedSize(10, 19)
                dash.setStyleSheet(qss_document_page_dash(self.font_size_offset))
                row.addStretch(1)
                row.addWidget(first_edit)
                row.addWidget(dash)
                row.addWidget(last_edit)
                row.addStretch(1)

                def save_range(_path=path, _first=first_edit, _last=last_edit):
                    total = self.page_count(_path)
                    try:
                        a, b = int(_first.text()), int(_last.text())
                    except ValueError:
                        a, b = self.page_selections.get(_path, (1, total))
                    a = max(1, min(a, total))
                    b = max(a, min(b, total))
                    self.page_selections[_path] = (a, b)
                    self.rebuild_image_strip()
                    self._update_height()

                first_edit.editingFinished.connect(save_range)
                last_edit.editingFinished.connect(save_range)
            else:
                source = QPixmap(path)
                if source.isNull():
                    holder.deleteLater()
                    continue
                shown = source.scaled(
                    preview_w, cell_h - 10, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                rounded = QPixmap(shown.size())
                rounded.fill(Qt.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.Antialiasing, True)
                clip = QPainterPath()
                clip.addRoundedRect(QRectF(rounded.rect()), 7, 7)
                painter.setClipPath(clip)
                painter.drawPixmap(0, 0, shown)
                painter.end()
                label = QLabel(holder)
                label.setPixmap(rounded)
                label.setGeometry(
                    (cell_w - shown.width()) // 2,
                    (cell_h - shown.height()) // 2,
                    shown.width(),
                    shown.height(),
                )
            close = QPushButton("×", holder)
            close.setFixedSize(20, 20)
            close.move(cell_w - 22, 2)
            close.setCursor(Qt.PointingHandCursor)
            close.setStyleSheet(
                f"QPushButton{{background:{t.COLOR_TEXT_MUTED};color:{t.COLOR_TEXT_INVERSE};"
                f"border:1px solid {t.COLOR_BORDER};border-radius:10px;padding:0;"
                f"font-size:{15 + self.font_size_offset}px;font-weight:600;}}"
                f"QPushButton:hover{{background:{t.COLOR_TEXT_SECONDARY};}}"
            )
            close.clicked.connect(lambda _=False, p=path: self.remove_path(p))
            holder.set_close_button(close)
            self.image_strip_layout.addWidget(holder)

        margins = self.image_strip_layout.contentsMargins()
        spacing = self.image_strip_layout.spacing()
        total_width = (
            margins.left() + margins.right() + len(self.paths) * cell_w
            + max(0, len(self.paths) - 1) * spacing
        )
        self.image_strip.setFixedSize(max(1, total_width), 116)
        self.image_scroll.setVisible(bool(self.paths))
        self.document_area.setVisible(bool(self.paths))
        self.image_strip.adjustSize()
        self.image_scroll.viewport().updateGeometry()

    def show_document(self, index=-1):
        if not self.paths:
            self.clear_image_strip()
            self.image_scroll.hide()
            self.document_area.hide()
            self._update_height()
            return
        self.rebuild_image_strip()
        self._update_height()

    def remove_current(self):
        if self.paths:
            path = self.paths.pop()
            self.page_selections.pop(path, None)
            self.show_document(len(self.paths) - 1)
