"""Point d'entrée unique FTNC pour l'interface et FastMCP."""
from __future__ import annotations

from typing import Any

from core.mcp_compat import FastMCP

from .generator import traiter_fiche_ftnc

mcp = FastMCP('ftnc_local')

@mcp.tool(name='traiter_fiche_ftnc', description='Parcours FTNC unique : extrait la fiche NQ DOCX locale, recherche la référence et les FTNC, pose les questions utiles et ne génère qu’après confirmation explicite.')
def outil_traiter_fiche_ftnc(
    chemin_docx: str,
    reference_confirmee: str = '',
    type_ftnc: str = '',
    corrections_json: str = '',
    confirmer_generation: bool = False,
) -> dict[str, Any]:
    """Démarrer avec chemin_docx seul, puis rappeler avec les réponses validées."""
    return traiter_fiche_ftnc(chemin_docx, reference_confirmee, type_ftnc,
                             corrections_json, confirmer_generation)

class FtncLocalSkill:
    name = 'ftnc_local'
    display_name = 'FTNC locale'
    icon = 'icon.svg'
    mcp = mcp

    def get_tools(self) -> list[dict[str, Any]]:
        return [{
            'name': 'traiter_fiche_ftnc',
            'description': 'Analyser une NQ DOCX locale, vérifier article et FTNC, demander les informations manquantes puis générer après confirmation.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'chemin_docx': {'type': 'string', 'description': 'Chemin local ou lien file:/// vers le DOCX NQ.'},
                    'reference_confirmee': {'type': 'string', 'description': 'PNR confirmé ou corrigé par l’utilisateur.'},
                    'type_ftnc': {'type': 'string', 'description': 'Type FTNC fourni par l’utilisateur.'},
                    'corrections_json': {'type': 'string', 'description': 'Objet JSON sérialisé de corrections des champs extraits.'},
                    'confirmer_generation': {'type': 'boolean', 'description': 'True seulement si l’utilisateur a explicitement demandé la génération.'},
                },
                'required': ['chemin_docx'],
                'additionalProperties': False,
            },
            'function': outil_traiter_fiche_ftnc,
        }]
