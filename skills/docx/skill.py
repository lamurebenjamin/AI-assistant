from __future__ import annotations

from .generator import Nouveau_Document


class DocxSkill:
    """Skill de création de documents Microsoft Word."""

    name = "docx"
    display_name = "Word"
    icon = "icon.svg"

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
