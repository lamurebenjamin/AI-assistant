from __future__ import annotations

from core.mcp_compat import FastMCP

from .generator import create_pdf as _generate_pdf

mcp = FastMCP("pdf")


@mcp.tool(
    name="create_pdf",
    description=(
        "Crée un document PDF dans le dossier output du projet à partir "
        "d'un titre et de paragraphes. Utilise cet outil lorsque "
        "l'utilisateur demande réellement de créer un fichier PDF."
    ),
)
def create_pdf(filename: str, title: str, paragraphs: list[str]) -> str:
    """Crée un document PDF dans output/ et retourne son chemin absolu."""
    return _generate_pdf(filename=filename, title=title, paragraphs=paragraphs)


class PdfSkill:
    """Skill de création de documents PDF basé sur FastMCP."""

    name = "pdf"
    icon = "icon.svg"
    mcp = mcp

    def get_tools(self):
        return [
            {
                "name": "create_pdf",
                "description": (
                    "Crée un document PDF dans le dossier output du projet à partir "
                    "d'un titre et de paragraphes. Utilise cet outil lorsque "
                    "l'utilisateur demande réellement de créer un fichier PDF."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Nom du fichier à créer, avec ou sans l'extension .pdf.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Titre principal du document PDF.",
                        },
                        "paragraphs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste ordonnée des paragraphes du document PDF.",
                        },
                    },
                    "required": ["filename", "title", "paragraphs"],
                    "additionalProperties": False,
                },
                "function": create_pdf,
            }
        ]
