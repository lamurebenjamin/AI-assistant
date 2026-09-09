from __future__ import annotations

from pathlib import Path
from typing import List

from docx import Document
from docx.shared import Pt


def create_docx(filename: str, title: str, paragraphs: List[str]) -> str:
    """Crée un DOCX dans output/ et retourne son chemin absolu."""
    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = str(filename).strip()
    if not filename:
        raise ValueError("Le nom du fichier est obligatoire.")
    if not filename.lower().endswith(".docx"):
        filename += ".docx"

    # Empêche le tool d'écrire en dehors de output/.
    safe_name = Path(filename).name
    if safe_name in {".", ".."}:
        raise ValueError("Nom de fichier invalide.")

    output_path = output_dir / safe_name

    document = Document()
    document.add_heading(str(title).strip() or "Document", level=1)

    for paragraph in paragraphs or []:
        document.add_paragraph(str(paragraph))

    normal_style = document.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(10)

    document.save(output_path)
    return str(output_path.resolve())
