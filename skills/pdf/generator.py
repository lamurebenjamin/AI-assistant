from __future__ import annotations

from pathlib import Path
from typing import List

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape


def create_pdf(filename: str, title: str, paragraphs: List[str]) -> str:
    """Cree un PDF dans output/ et retourne son chemin absolu."""
    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = str(filename).strip()
    if not filename:
        raise ValueError("Le nom du fichier PDF est obligatoire.")
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    # Empeche l'ecriture en dehors du dossier output/.
    safe_name = Path(filename).name
    if safe_name in {".", ".."}:
        raise ValueError("Nom de fichier PDF invalide.")
    output_path = output_dir / safe_name

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=str(title).strip() or "Document PDF",
        author="PDF Skill",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PdfTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=HexColor("#1F4E78"),
        alignment=TA_LEFT,
        spaceAfter=10 * mm,
    )
    body_style = ParagraphStyle(
        "PdfBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=HexColor("#202020"),
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    )

    story = [Paragraph(escape(str(title).strip() or "Document PDF"), title_style)]
    for paragraph in paragraphs or []:
        text = escape(str(paragraph)).replace("\n", "<br/>")
        story.append(Paragraph(text or " ", body_style))
        story.append(Spacer(1, 1 * mm))

    document.build(story)
    return str(output_path.resolve())
