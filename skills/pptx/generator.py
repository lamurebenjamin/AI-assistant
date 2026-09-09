from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches, Pt

DEFAULT_TEMPLATE_NAME = "template.pptx"
TITLE_TYPES = {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE}
CONTENT_TYPES = {PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _template_path(template_name: Optional[str]) -> Path:
    name = Path(str(template_name or DEFAULT_TEMPLATE_NAME).strip()).name
    if not name.lower().endswith(".pptx"):
        name += ".pptx"
    path = Path(__file__).resolve().parent / "templates" / name
    if not path.is_file():
        raise FileNotFoundError(f"Template PowerPoint introuvable : {path}")
    return path


def _output_path(filename: str) -> Path:
    name = str(filename).strip()
    if not name:
        raise ValueError("Le nom du fichier PowerPoint est obligatoire.")
    if not name.lower().endswith(".pptx"):
        name += ".pptx"
    output = _project_root() / "output" / Path(name).name
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def _placeholder_type(shape):
    try:
        return shape.placeholder_format.type if shape.is_placeholder else None
    except (AttributeError, ValueError):
        return None


def _text_shapes(slide):
    return [shape for shape in slide.shapes if getattr(shape, "has_text_frame", False)]


def _title_shape(slide):
    if slide.shapes.title is not None:
        return slide.shapes.title
    for shape in slide.placeholders:
        if _placeholder_type(shape) in TITLE_TYPES and shape.has_text_frame:
            return shape
    shapes = _text_shapes(slide)
    return shapes[0] if shapes else None


def _content_shape(slide, excluded=None):
    excluded_ids = {id(shape) for shape in (excluded or []) if shape is not None}
    candidates = [
        shape for shape in slide.placeholders
        if id(shape) not in excluded_ids
        and shape.has_text_frame
        and _placeholder_type(shape) in CONTENT_TYPES | {PP_PLACEHOLDER.SUBTITLE}
    ]
    if not candidates:
        candidates = [shape for shape in _text_shapes(slide) if id(shape) not in excluded_ids]
    return max(candidates, key=lambda shape: shape.width * shape.height) if candidates else None


def _add_textbox(slide, x, y, w, h):
    shape = slide.shapes.add_textbox(x, y, w, h)
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.TOP
    return shape


def _set_title(shape, text: str, fallback: bool = False) -> None:
    shape.text = text
    if fallback:
        p = shape.text_frame.paragraphs[0]
        p.font.name = "Arial"
        p.font.size = Pt(26)
        p.font.bold = True
        p.font.color.rgb = RGBColor(31, 78, 120)


def _set_list(shape, values: List[Any], fallback: bool = False) -> None:
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    for index, value in enumerate(values):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.text = str(value)
        p.level = 0
        p.space_after = Pt(8)
        if fallback:
            p.font.name = "Arial"
            p.font.size = Pt(20)
            p.font.color.rgb = RGBColor(32, 32, 32)


def _keep_first_two_slides(presentation) -> None:
    for slide_id in list(presentation.slides._sldIdLst)[2:]:
        presentation.part.drop_rel(slide_id.rId)
        presentation.slides._sldIdLst.remove(slide_id)


def _content_layout(presentation):
    preferred = {"titre et contenu", "title and content", "contenu", "content"}
    for layout in presentation.slide_layouts:
        types = {_placeholder_type(shape) for shape in layout.placeholders}
        if str(layout.name or "").strip().casefold() in preferred and types & TITLE_TYPES and types & CONTENT_TYPES:
            return layout
    for layout in presentation.slide_layouts:
        types = {_placeholder_type(shape) for shape in layout.placeholders}
        if types & TITLE_TYPES and types & CONTENT_TYPES:
            return layout
    for layout in presentation.slide_layouts:
        if str(layout.name or "").strip().casefold() in {"vide", "blank"}:
            return layout
    return presentation.slide_layouts[0]


def create_pptx(
    filename: str,
    title: str,
    subtitle: str,
    slides: List[Dict[str, Any]],
    template_name: Optional[str] = None,
) -> str:
    """Cree un PPTX. Le slide 1 est la couverture et le slide 2 le sommaire."""
    items = slides or []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or "title" not in item or "bullets" not in item:
            raise ValueError(f"La diapositive {index} doit contenir 'title' et 'bullets'.")
        if not isinstance(item["bullets"], list):
            raise ValueError(f"Le champ 'bullets' de la diapositive {index} doit etre une liste.")

    presentation = Presentation(str(_template_path(template_name)))
    if len(presentation.slides) < 2:
        raise ValueError(
            "Le template doit contenir au moins deux diapositives : "
            "la couverture en position 1 et le sommaire en position 2."
        )

    _keep_first_two_slides(presentation)
    cover = presentation.slides[0]
    summary = presentation.slides[1]

    cover_title = _title_shape(cover)
    cover_title_fallback = cover_title is None
    if cover_title is None:
        cover_title = _add_textbox(cover, Inches(0.8), Inches(1.4), Inches(11.7), Inches(1.2))
    _set_title(cover_title, str(title).strip() or "Presentation", cover_title_fallback)

    if str(subtitle).strip():
        subtitle_shape = _content_shape(cover, [cover_title])
        subtitle_fallback = subtitle_shape is None
        if subtitle_shape is None:
            subtitle_shape = _add_textbox(cover, Inches(0.8), Inches(3.0), Inches(11.0), Inches(0.9))
        subtitle_shape.text = str(subtitle).strip()
        if subtitle_fallback:
            p = subtitle_shape.text_frame.paragraphs[0]
            p.font.name = "Arial"
            p.font.size = Pt(18)

    summary_title = _title_shape(summary)
    summary_title_fallback = summary_title is None
    if summary_title is None:
        summary_title = _add_textbox(summary, Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.8))
    _set_title(summary_title, "Sommaire", summary_title_fallback)

    summary_content = _content_shape(summary, [summary_title])
    summary_fallback = summary_content is None
    if summary_content is None:
        summary_content = _add_textbox(summary, Inches(1.0), Inches(1.6), Inches(11.0), Inches(4.9))
    summary_entries = [
        f"{index}. {str(item['title']).strip() or f'Diapositive {index}'}"
        for index, item in enumerate(items, start=1)
    ]
    _set_list(summary_content, summary_entries, summary_fallback)

    layout = _content_layout(presentation)
    for index, item in enumerate(items, start=1):
        slide = presentation.slides.add_slide(layout)
        title_shape = _title_shape(slide)
        title_fallback = title_shape is None
        if title_shape is None:
            title_shape = _add_textbox(slide, Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.8))
        _set_title(title_shape, str(item["title"]).strip() or f"Diapositive {index}", title_fallback)

        body = _content_shape(slide, [title_shape])
        body_fallback = body is None
        if body is None:
            body = _add_textbox(slide, Inches(1.0), Inches(1.6), Inches(11.0), Inches(4.9))
        _set_list(body, item["bullets"], body_fallback)

    output = _output_path(filename)
    presentation.save(output)
    return str(output.resolve())
