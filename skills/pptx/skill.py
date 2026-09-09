from __future__ import annotations

from .generator import create_pptx


class PptxSkill:
    """Skill de création de présentations Microsoft PowerPoint."""

    name = "pptx"

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