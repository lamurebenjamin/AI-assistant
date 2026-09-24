"""Document source capture rendering for DocumentDialog."""

import base64
import html
import json
import os
import re
import tempfile
import time
from pathlib import Path

from PySide6.QtGui import QPixmap

try:
    import fitz
except ImportError:
    fitz = None

import src.ui.design_tokens as t
from src.config.schema import LOGGER


class DocumentSourceRenderer:
    """Builds source preview HTML and registers generated temporary files."""

    def __init__(self, dialog):
        self.dialog = dialog

    def _add_sources_html(self, answer, documents):
        dialog = self.dialog
        if fitz is None or not answer.strip(): return ""
        by_name={}
        for document in documents:
            path=document.get("path") if isinstance(document,dict) else document
            if path: by_name[os.path.basename(path).casefold()]=path
        citations=re.findall(r"([^\n/\\]+?\.pdf)\s*[—-]\s*(?:p(?:age)?\.?\s*)?(\d+)(?:\s*\n+\s*>?\s*(?:Extrait\s*:\s*)?([^\n]+))?",answer,re.IGNORECASE)
        cards=[]
        for index,(filename,page_text,excerpt) in enumerate(citations):
            path=by_name.get(os.path.basename(filename.strip()).casefold())
            if not path: continue
            try:
                doc=fitz.open(path); total=doc.page_count; page_number=max(1,int(page_text))
                if page_number>total: doc.close(); continue
                page=doc.load_page(page_number-1); needle=excerpt.strip().strip(" \t\r\n\"'«»"); rects=page.search_for(needle) if len(needle)>=8 else []
                if not rects and len(needle)>80: rects=page.search_for(needle[:80])
                clip=page.rect
                if rects:
                    union=fitz.Rect(rects[0])
                    for rect in rects[1:]: union|=rect
                    clip=fitz.Rect(max(page.rect.x0,union.x0-28),max(page.rect.y0,union.y0-42),min(page.rect.x1,union.x1+28),min(page.rect.y1,union.y1+42))
                    highlight=page.add_highlight_annot(rects); highlight.set_colors(stroke=(0.55, 0.92, 0.66)); highlight.update()
                # Conserve une capture haute définition distincte pour la loupe
                # et la fenêtre x2. Les anciens tours ne sont plus écrasés car le
                # nom contient un identifiant unique par capture.
                capture_id = f"{time.monotonic_ns()}_{index}"
                pix=page.get_pixmap(matrix=fitz.Matrix(3.0,3.0),clip=clip,alpha=False,annots=True)
                image_path=os.path.join(tempfile.gettempdir(),f"assistant_source_{os.getpid()}_{capture_id}.png")
                pix.save(image_path); doc.close()
                dialog._temp_files.add(image_path)
                source_pixmap=QPixmap(image_path)
                max_w=max(120,dialog.width()-82)
                display_w=min(source_pixmap.width(), max_w)
                display_h=max(1, round(source_pixmap.height() * display_w / max(1, source_pixmap.width())))
                token=base64.urlsafe_b64encode(os.path.basename(path).encode("utf-8")).decode("ascii").rstrip("=")
                href=f"source:{page_number}:{token}"; uri=Path(image_path).as_uri(); title=html.escape(os.path.splitext(os.path.basename(path))[0])
                source_title = f"{os.path.splitext(os.path.basename(path))[0]} (Page {page_number}/{total})"
                image_payload = json.dumps(
                    {"path": image_path, "title": source_title},
                    ensure_ascii=False,
                ).encode("utf-8")
                image_token = base64.urlsafe_b64encode(image_payload).decode("ascii").rstrip("=")
                image_href = f"sourceimage:{image_token}"
                cards.append(
                    f'<div style="margin-top:12px; padding-top:9px; border-top:1px solid {t.COLOR_SUCCESS_BORDER};">'
                    f'<div style="font-size:{10 + dialog.FONT_SIZE_OFFSET}px; font-style:italic; color:{t.COLOR_SUCCESS_TEXT};">'
                    f'Source : <a href="{href}" style="color:{t.COLOR_SUCCESS}; text-decoration:none;">'
                    f'{title} (Page {page_number}/{total})</a></div>'
                    # Le navigateur affiche la capture réduite via width/height,
                    # mais conserve le fichier haute définition comme ressource.
                    # La loupe x2 prélève donc directement des pixels nets.
                    f'<div style="margin-top:8px;"><a href="{image_href}">'
                    f'<img src="{uri}" width="{display_w}" height="{display_h}" />'
                    f'</a></div></div>'
                )
            except Exception: LOGGER.exception("Impossible de générer la capture de la source")  # noqa: BLE001
        if not cards: return ""
        return ''.join(cards)


