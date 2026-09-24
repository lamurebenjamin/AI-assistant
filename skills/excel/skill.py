from __future__ import annotations

from typing import Any

from core.mcp_compat import FastMCP

from .generator import create_excel as _generate_excel

mcp = FastMCP("excel")


@mcp.tool(
    name="create_excel",
    description=(
        "Crée un classeur Microsoft Excel (.xlsx) dans le dossier output du projet "
        "à partir d'un nom de feuille, d'en-têtes et de lignes de données. "
        "Utilise cet outil lorsque l'utilisateur demande réellement de créer "
        "un fichier Excel."
    ),
)
def create_excel(
    filename: str,
    sheet_name: str,
    headers: list[str],
    rows: list[list[Any]],
) -> str:
    """Crée un classeur Excel XLSX dans output/ et retourne son chemin absolu."""
    return _generate_excel(
        filename=filename,
        sheet_name=sheet_name,
        headers=headers,
        rows=rows,
    )


class ExcelSkill:
    """Skill de création de classeurs Microsoft Excel basé sur FastMCP."""

    name = "excel"
    icon = "icon.svg"
    mcp = mcp

    def get_tools(self):
        return [
            {
                "name": "create_excel",
                "description": (
                    "Crée un classeur Microsoft Excel (.xlsx) dans le dossier output du projet "
                    "à partir d'un nom de feuille, d'en-têtes et de lignes de données. "
                    "Utilise cet outil lorsque l'utilisateur demande réellement de créer "
                    "un fichier Excel."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": (
                                "Nom du fichier Excel à créer, avec ou sans l'extension .xlsx."
                            ),
                        },
                        "sheet_name": {
                            "type": "string",
                            "description": "Nom de la feuille Excel.",
                        },
                        "headers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste ordonnée des en-têtes de colonnes.",
                        },
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": [
                                        "string",
                                        "number",
                                        "integer",
                                        "boolean",
                                        "null",
                                    ]
                                },
                            },
                            "description": "Liste ordonnée des lignes du tableau Excel.",
                        },
                    },
                    "required": ["filename", "sheet_name", "headers", "rows"],
                    "additionalProperties": False,
                },
                "function": create_excel,
            }
        ]
