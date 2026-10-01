"""Adaptateur des données Excel de FTNC vers la conversation."""
from .ftnc_card_parser import ftnc_reference_from_output


def load_ftnc_cards(turn, raw, tool_name):
    """Charge une seule fois les cartes; une erreur de lecture reste visible."""
    if 'ftnc_cards_data' in turn or 'ftnc_cards_error' in turn:
        return
    try:
        from skills.ftnc.generator import ftnc_cartes_suivi
        reference = ftnc_reference_from_output(raw) if tool_name == 'Details' else ''
        turn['ftnc_cards_data'] = ftnc_cartes_suivi(reference)
    except (OSError, ValueError, ImportError, KeyError) as exc:
        turn['ftnc_cards_error'] = str(exc)
        return
    try:
        from skills.ftnc.generator import ftnc_absentes_du_suivi
        turn['ftnc_missing_planner'] = ftnc_absentes_du_suivi(reference)
    except (OSError, ValueError, ImportError, KeyError) as exc:
        turn['ftnc_missing_error'] = str(exc)
