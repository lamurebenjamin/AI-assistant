"""Outil FastMCP et wrapper UI pour le skill PNR."""
from __future__ import annotations

from typing import Any

from core.mcp_compat import FastMCP

from .generator import rechercher_reference

mcp = FastMCP("pnr")


@mcp.tool(
    name="rechercher_reference_pnr",
    description=(
        "Recherche une reference exacte dans PNR.db, remonte a chaque racine "
        "et affiche les chemins de nomenclature jusqu'a la reference."
    ),
)
def rechercher_reference_pnr(reference: str) -> str:
    """Retourne les nomenclatures qui contiennent une reference.

    Args:
        reference: Reference article exacte a rechercher dans PNR.db.
    """
    return rechercher_reference(reference)


class PnrSkill:
    """Wrapper de decouverte UI et compatibilite outils LLM."""
    name = "pnr"  # Identifiant interne conserve pour ne pas casser la configuration.
    display_name = "Nomenclature"
    icon = "icon.svg"
    mcp = mcp

    def get_tools(self) -> list[dict[str, Any]]:
        """Expose l'outil au SkillManager et a l'interface."""
        return [{
            "name": "rechercher_reference_pnr",
            "description": "Recherche une reference et affiche ses nomenclatures.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference article exacte a rechercher",
                    },
                },
                "required": ["reference"],
                "additionalProperties": False,
            },
            "function": rechercher_reference_pnr,
        }]
