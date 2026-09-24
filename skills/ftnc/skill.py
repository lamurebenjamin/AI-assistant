from __future__ import annotations

from core.mcp_compat import FastMCP

from .generator import ftnc_details as _ftnc_details
from .generator import ftnc_liste as _ftnc_liste

mcp = FastMCP("FTNC")


@mcp.tool(
    name="Liste",
    description=(
        "Liste les FTNC non démarrées ou en cours présentes dans le planner, "
        "triées par priorité, puis identifie les FTNC en cours du suivi €uro qui ne sont "
        "pas encore présentes dans le planner. Utiliser cet outil pour un état des lieux, "
        "une liste, une synthèse ou pour rechercher les nouvelles FTNC à ajouter au planner."
    ),
)
def Liste() -> str:
    """Liste les FTNC en cours et les nouvelles FTNC."""
    return _ftnc_liste()


# Marqueur pour retour direct sans ré-analyse LLM
Liste.return_direct = True


@mcp.tool(
    name="Details",
    description=(
        "Recherche et affiche les détails d'une FTNC dans le planner et dans le "
        "suivi €uro à partir d'une référence complète ou partielle. La recherche accepte "
        "notamment une référence préfixée MWB ou VLB, un numéro ou son identifiant numérique."
    ),
)
def Details(reference: str) -> str:
    """Recherche et affiche les détails d'une FTNC."""
    return _ftnc_details(reference)


Details.return_direct = True


class FtncSkill:
    """Skill de consultation des FTNC basé sur FastMCP."""

    name = "FTNC"
    icon = "icon.png"
    mcp = mcp

    def get_tools(self):
        return [
            {
                "name": "Liste",
                "description": (
                    "Liste les FTNC non démarrées ou en cours présentes dans le planner, "
                    "triées par priorité, puis identifie les FTNC en cours du suivi €uro qui ne sont "
                    "pas encore présentes dans le planner. Utiliser cet outil pour un état des lieux, "
                    "une liste, une synthèse ou pour rechercher les nouvelles FTNC à ajouter au planner."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                "function": Liste,
                "return_direct": True,
            },
            {
                "name": "Details",
                "description": (
                    "Recherche et affiche les détails d'une FTNC dans le planner et dans le "
                    "suivi €uro à partir d'une référence complète ou partielle. La recherche accepte "
                    "notamment une référence préfixée MWB ou VLB, un numéro ou son identifiant numérique."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reference": {
                            "type": "string",
                            "description": (
                                "Référence complète ou partielle de la FTNC, par exemple MWB1234567890, "
                                "VLB1234567890 ou 1234567890."
                            ),
                        }
                    },
                    "required": ["reference"],
                    "additionalProperties": False,
                },
                "function": Details,
                "return_direct": True,
            },
        ]
