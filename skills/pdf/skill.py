from __future__ import annotations

from .generator import create_pdf


class PdfSkill:
    """Skill de creation de documents PDF."""

    name = "pdf"

    def get_tools(self):
        return [
            {
                "name": "create_pdf",
                "description": (
                    "Cree un document PDF dans le dossier output du projet a partir "
                    "d'un titre et de paragraphes. Utilise cet outil lorsque "
                    "l'utilisateur demande reellement de creer un fichier PDF."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Nom du fichier a creer, avec ou sans l'extension .pdf.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Titre principal du document PDF.",
                        },
                        "paragraphs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste ordonnee des paragraphes du document PDF.",
                        },
                    },
                    "required": ["filename", "title", "paragraphs"],
                    "additionalProperties": False,
                },
                "function": create_pdf,
            }
        ]
