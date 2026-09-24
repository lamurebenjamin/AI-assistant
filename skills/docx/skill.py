from __future__ import annotations

from core.mcp_compat import FastMCP

from .generator import Nouveau_Document as _generate_docx

mcp = FastMCP("docx")


@mcp.tool(
    name="Nouveau_Document",
    description=(
        "Crée un document Microsoft Word (.docx) dans le dossier output du projet "
        "à partir d'un titre et de paragraphes. Utilise cet outil lorsque l'utilisateur "
        "demande réellement de créer un fichier Word."
    ),
)
def Nouveau_Document(filename: str, title: str, paragraphs: list[str]) -> str:
    """Crée un document Word dans output/ et retourne son chemin absolu."""
    return _generate_docx(filename=filename, title=title, paragraphs=paragraphs)


class DocxSkill:
    """Skill de création de documents Microsoft Word basé sur FastMCP."""

    name = "docx"
    display_name = "Word"
    icon = "icon.svg"
    mcp = mcp

    def get_tools(self):
        return [
            {
                "name": "Nouveau_Document",
                "description": (
                    "Crée un document Microsoft Word (.docx) dans le dossier output du projet "
                    "à partir d'un titre et de paragraphes. Utilise cet outil lorsque l'utilisateur "
                    "demande réellement de créer un fichier Word."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Nom du fichier à créer, avec ou sans l'extension .docx.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Titre principal du document.",
                        },
                        "paragraphs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste ordonnée des paragraphes du document.",
                        },
                    },
                    "required": ["filename", "title", "paragraphs"],
                    "additionalProperties": False,
                },
                "function": Nouveau_Document,
            }
        ]
