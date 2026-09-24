"""Formatage des fichiers produits par les tools pour l'interface assistant."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.config.schema import APP_DIR


def created_file_paths(detail: str | None) -> list[str]:
    """Extrait les chemins de fichiers existants d'un résultat de skill."""
    try:
        payload: Any = json.loads(detail or "null")
    except (json.JSONDecodeError, TypeError):
        payload = detail
    values: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple, set)):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            values.append(value.strip())

    visit(payload)
    extensions = {".docx", ".pdf", ".xlsx", ".xls", ".pptx", ".csv", ".txt"}
    found: list[str] = []
    for value in values:
        if not value or Path(value).suffix.lower() not in extensions:
            continue
        candidate = os.path.expandvars(os.path.expanduser(value))
        if not os.path.isabs(candidate):
            candidate = os.path.join(APP_DIR, candidate)
        candidate = os.path.normpath(candidate)
        if os.path.isfile(candidate) and candidate not in found:
            found.append(candidate)
    return found


def file_link_markdown(path: str) -> str:
    """Construit le lien Markdown affichant un fichier produit."""
    display_name = Path(path).stem
    return f"📄 [{display_name}]({Path(path).resolve().as_uri()})\n"
