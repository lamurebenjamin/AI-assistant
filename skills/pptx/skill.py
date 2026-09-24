from __future__ import annotations

from typing import Any

from core.mcp_compat import FastMCP

from .generator import create_pptx as _generate_pptx

mcp = FastMCP("pptx")


@mcp.tool(
    name="create_pptx",
    description=(
        "Crée une présentation Microsoft PowerPoint au format .pptx à partir d'un "
        "titre, d'un sous-titre et d'une liste de diapositives."
    ),
)
def create_pptx(
    filename: str,
    title: str,
    subtitle: str,
    slides: list[dict[str, Any]],
    template_name: str | None = None,
) -> str:
    """Crée un PPTX dans output/ et retourne son chemin absolu."""
    return _generate_pptx(
        filename=filename,
        title=title,
        subtitle=subtitle,
        slides=slides,
        template_name=template_name,
    )


class PptxSkill:
    """Skill de création de présentations Microsoft PowerPoint basé sur FastMCP."""

    name = "pptx"
    icon = "icon.svg"
    mcp = mcp

    def get_tools(self):
        return [
            {
                "name": "create_pptx",
                "description": (
                    "Crée une présentation Microsoft PowerPoint "
                    "au format .pptx à partir d'un template, "
                    "d'un titre, d'un sous-titre et d'une liste "
                    "de diapositives."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": (
                                "Nom du fichier PowerPoint à créer, "
                                "avec ou sans l'extension .pptx."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Titre principal de la présentation."
                            ),
                        },
                        "subtitle": {
                            "type": "string",
                            "description": (
                                "Sous-titre de la couverture."
                            ),
                        },
                        "slides": {
                            "type": "array",
                            "description": (
                                "Liste ordonnée des diapositives."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": (
                                            "Titre de la diapositive."
                                        ),
                                    },
                                    "bullets": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": (
                                            "Liste ordonnée des points "
                                            "de la diapositive."
                                        ),
                                    },
                                },
                                "required": [
                                    "title",
                                    "bullets",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "template_name": {
                            "type": "string",
                            "description": (
                                "Nom du template présent dans le "
                                "dossier templates/. "
                                "Par défaut : template.pptx."
                            ),
                        },
                    },
                    "required": [
                        "filename",
                        "title",
                        "subtitle",
                        "slides",
                    ],
                    "additionalProperties": False,
                },
                "function": create_pptx,
            }
        ]