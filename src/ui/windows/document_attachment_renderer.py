"""Vignettes des documents associes aux tours de conversation."""
import html
import os
import re
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None
import src.ui.design_tokens as t
from src.config.schema import LOGGER


def _answer_without_sources(self, answer):
    if not answer:
        return ""
    clean = re.split(r"(?im)^\s*#{2,3}\s*Sources\s*$", answer, maxsplit=1)[0]
    clean = re.split(r"(?im)^\s*Sources\s*:\s*$", clean, maxsplit=1)[0]
    # Certains modèles ajoutent des retours à la ligne avant ou après la
    # réponse. Ils ne doivent pas créer d'espace visuel parasite autour de
    # la bulle, sans modifier les retours à la ligne internes.
    return clean.lstrip().rstrip()


def _attachment_preview_html(self, documents):
    """Crée les vignettes à conserver dans la bulle de la demande utilisateur."""
    cards = []
    for index, document in enumerate(documents or []):
        path = document.get("path") if isinstance(document, dict) else document
        if not path or not os.path.isfile(path):
            continue
        pages = document.get("pages", []) if isinstance(document, dict) else []
        is_pdf = path.lower().endswith(".pdf")
        preview_path = path
        page_caption = ""

        if is_pdf:
            first = int(pages[0]) if pages else 1
            last = int(pages[-1]) if pages else first
            page_caption = str(first) if first == last else f"{first} - {last}"
            if fitz is not None:
                try:
                    doc = fitz.open(path)
                    try:
                        page_number = max(1, min(first, doc.page_count))
                        pix = doc.load_page(page_number - 1).get_pixmap(
                            matrix=fitz.Matrix(1.0, 1.0), alpha=False
                        )
                        preview_path = os.path.join(
                            tempfile.gettempdir(),
                            f"assistant_turn_attachment_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
                        )
                        pix.save(preview_path)
                        self._temp_files.add(preview_path)
                    finally:
                        doc.close()
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Impossible de générer la vignette jointe du PDF")
                    preview_path = ""

        if is_pdf and (not preview_path or not os.path.isfile(preview_path)):
            preview_path = os.path.join(
                tempfile.gettempdir(),
                f"assistant_turn_attachment_fb_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
            )
            fb_pix = self._create_pdf_fallback_pixmap(68, 88)
            fb_pix.save(preview_path, "PNG")
            self._temp_files.add(preview_path)

        if not preview_path or not os.path.isfile(preview_path):
            continue

        pixmap = QPixmap(preview_path)
        if pixmap.isNull():
            continue
        # Une vignette de document et sa ligne de pages ont la même hauteur
        # totale qu'une vignette d'image seule.
        total_h = t.DOCUMENT_THUMBNAIL_HEIGHT
        caption_h = 16 if is_pdf else 0
        image_h = total_h - caption_h
        shown = pixmap.scaled(t.DOCUMENT_THUMBNAIL_WIDTH, image_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        rendered_path = os.path.join(
            tempfile.gettempdir(),
            f"assistant_turn_rendered_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
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
        rounded.save(rendered_path, "PNG")
        self._temp_files.add(rendered_path)
        uri = Path(rendered_path).as_uri()

        caption = (
            f'<div style="height:{caption_h}px; line-height:{caption_h}px; '
            f'text-align:center; font-size:{10 + self.FONT_SIZE_OFFSET}px; color:{t.COLOR_STATUS_SUBTLE};">'
            f'{html.escape(page_caption)}</div>'
            if is_pdf else ""
        )
        cards.append(
            '<td valign="top" style="padding-right:8px;">'
            f'<div style="width:82px; height:{total_h}px; text-align:center;">'
            f'<div style="height:{image_h}px; line-height:{image_h}px;">'
            f'<img src="{uri}" /></div>{caption}</div></td>'
        )

    if not cards:
        return ""
    return (
        '<div style="margin-top:8px; overflow:hidden;">'
        '<table cellspacing="0" cellpadding="0" border="0"><tr>'
        + "".join(cards)
        + '</tr></table></div>'
    )


def _create_pdf_fallback_pixmap(width: int, height: int) -> QPixmap:
    """Crée une vignette neutre lorsque le rendu PDF n'est pas disponible."""
    pixmap = QPixmap(max(1, int(width)), max(1, int(height)))
    pixmap.fill(QColor(t.COLOR_PREVIEW_BACKGROUND))
    painter = QPainter(pixmap)
    painter.setPen(QPen(QColor(t.COLOR_BORDER), 1))
    painter.drawRect(pixmap.rect().adjusted(1, 1, -2, -2))
    painter.setPen(QColor(t.COLOR_TEXT_SECONDARY))
    painter.setFont(QFont("Arial", max(8, min(14, int(width / 7)))))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "PDF")
    painter.end()
    return pixmap
