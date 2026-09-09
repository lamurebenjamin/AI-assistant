# -*- coding: utf-8 -*-
"""Utilitaires d'extraction et de manipulation de documents PDF."""

import base64
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def normalize_page_selection(selection, page_count: int) -> List[int]:
    """Normalise une saisie `1-3, 7` ou une liste `[1, 2, 3, 7]`."""
    if page_count <= 0:
        return []

    if selection is None:
        return list(range(1, page_count + 1))

    if isinstance(selection, (list, tuple, set, range)):
        try:
            pages = {int(page) for page in selection}
        except (TypeError, ValueError):
            raise ValueError("La sélection de pages contient une valeur non numérique.")
    else:
        value = str(selection).strip()
        if value.lower() in {"", "tout", "toutes", "all", "*"}:
            return list(range(1, page_count + 1))

        value = value.strip("[](){}")
        pages = set()
        for token in re.split(r"[;,\s]+", value):
            if not token:
                continue
            if "-" in token:
                left, right = token.split("-", 1)
                if not left.isdigit() or not right.isdigit():
                    raise ValueError(f"Sélection de pages invalide : {token}")
                first, last = sorted((int(left), int(right)))
                pages.update(range(first, last + 1))
            elif token.isdigit():
                pages.add(int(token))
            else:
                raise ValueError(f"Sélection de pages invalide : {token}")

    invalid = sorted(page for page in pages if page < 1 or page > page_count)
    if invalid:
        raise ValueError(
            f"Page hors limites : {invalid[0]} (document de {page_count} pages)"
        )
    return sorted(pages)


def extract_pdf_context(
    path: str, selected_pages=None, max_rendered_pages: int = 4
) -> Tuple[List[dict], List[dict], int]:
    """Extrait le texte des pages sélectionnées et rend les pages sans texte en image."""
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF n'est pas installé. Installez-le avec : "
            f'"{sys.executable}" -m pip install pymupdf'
        )
    pages, rendered = [], []
    doc = fitz.open(path)
    try:
        page_count = doc.page_count
        chosen = normalize_page_selection(selected_pages, page_count)
        for page_number in chosen:
            page = doc.load_page(page_number - 1)
            extracted = page.get_text("text").strip()
            if extracted:
                pages.append({"page": page_number, "text": extracted})
            elif len(rendered) < max_rendered_pages:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(140 / 72, 140 / 72), alpha=False
                )
                encoded = base64.b64encode(pix.tobytes("png")).decode("ascii")
                rendered.append({
                    "page": page_number,
                    "data_url": f"data:image/png;base64,{encoded}",
                })
        return pages, rendered, page_count
    finally:
        doc.close()


def open_pdf_at_page(path: str, page: int) -> bool:
    """Ouvre un PDF à la page citée, avec priorité à Adobe sous Windows."""
    path = os.path.abspath(path)
    page = max(1, int(page))
    if sys.platform == "win32":
        adobe_candidates = [
            os.path.join(
                os.environ.get("ProgramFiles", ""),
                "Adobe",
                "Acrobat DC",
                "Acrobat",
                "Acrobat.exe",
            ),
            os.path.join(
                os.environ.get("ProgramFiles(x86)", ""),
                "Adobe",
                "Acrobat Reader DC",
                "Reader",
                "AcroRd32.exe",
            ),
        ]
        for executable in adobe_candidates:
            if executable and os.path.isfile(executable):
                subprocess.Popen([executable, "/A", f"page={page}", path])
                return True
        uri = Path(path).as_uri() + f"#page={page}"
        os.startfile(uri)
        return True
    subprocess.Popen(["xdg-open", Path(path).as_uri() + f"#page={page}"])
    return True
