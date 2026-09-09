# -*- coding: utf-8 -*-
"""Construction des charges utiles documentaires multimodales (texte + images Base64)."""

import base64
import mimetypes
import os
from typing import List, Tuple

from src.documents.pdf_utils import extract_pdf_context

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}


def document_image_data_url(path: str) -> str:
    """Encode une image locale dans une data URL compatible OpenAI/llama.cpp."""
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def prepare_document_payload(
    documents: list, max_rendered_images: int = 4
) -> Tuple[List[str], List[dict], List[Tuple[str, int]]]:
    """Construit le contexte textuel, les blocs images et le catalogue de sources."""
    text_parts, image_parts, source_pages = [], [], []
    image_count = 0

    for document in documents:
        if isinstance(document, dict):
            path = document["path"]
            selected_pages = document.get("pages")
        else:
            path, selected_pages = document, None

        filename = os.path.basename(path)
        extension = os.path.splitext(path)[1].lower()

        if extension == ".pdf":
            pages, rendered, _ = extract_pdf_context(path, selected_pages)
            for item in pages:
                text_parts.append(
                    f"\n--- SOURCE: {filename} — PAGE {item['page']} ---\n"
                    f"{item['text']}\n--- FIN PAGE {item['page']} ---\n"
                )
                source_pages.append((filename, item["page"]))
            for item in rendered:
                if image_count >= max_rendered_images:
                    break
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": item["data_url"]},
                })
                source_pages.append((filename, item["page"]))
                image_count += 1
            if not pages and not rendered:
                text_parts.append(
                    f"\n--- SOURCE: {filename} ---\n"
                    "Aucun contenu exploitable dans les pages sélectionnées.\n"
                )
        elif extension in SUPPORTED_IMAGE_EXTENSIONS:
            if image_count < max_rendered_images:
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": document_image_data_url(path)},
                })
                image_count += 1
            source_pages.append((filename, 1))
        else:
            raise ValueError(f"Format non pris en charge : {filename}")

    return text_parts, image_parts, source_pages
