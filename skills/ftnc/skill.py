from __future__ import annotations

from .generator import ftnc_details, ftnc_liste


class FtncSkill:
    """Skill de consultation des FTNC présentes dans le planner et le suivi €uro."""

    name = "FTNC"
    icon = "icon.png"

    def get_tools(self):
        return [
            {
                "name": "Liste",
                "description": (
                    "Liste les FTNC non démarrées ou en cours présentes dans le planner, "
                    "triées par priorité, puis identifie les FTNC en cours du suivi €uro qui ne sont "
                    "pas encore présentes dans le planner. Utiliser cet outil pour un état des lieux, "
                    "une liste, une synthèse ou pour rechercher les nouvelles FTNC à ajouter  au planner."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                "function": ftnc_liste,
                "return_direct": True,
            },
            {
                "name": "Détails",
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
                "function": ftnc_details,
                "return_direct": True,
            },
        ]
