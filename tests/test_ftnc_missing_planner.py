"""Non-regression FTNC : sortie vide et references planner absentes du suivi filtre."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from skills.ftnc import generator as g
from src.ui.widgets.ftnc_card_data import load_ftnc_cards


class MissingPlannerTests(unittest.TestCase):
    def test_planner_reference_excluded_by_suivi_filter_is_reported(self):
        suivi = [{'reference': 'MWB1234567890', 'identifiant': '1234567890'}]
        df = pd.DataFrame({'ref': ['MWB1234567890', 'VLB9876543210', 'VLB9876543210', None]})
        with patch.object(g, '_lire_suivi', return_value=suivi), \
             patch.object(g, '_get_ftnc_config', return_value={'fichier_ftnc': Path('x.xlsx'),
                                                               'feuille_ftnc': 'Feuille'}), \
             patch.object(g, '_verifier', return_value=Path('x.xlsx')), \
             patch.object(g.pd, 'read_excel', return_value=df):
            self.assertEqual(g.ftnc_absentes_du_suivi(), ['VLB9876543210'])
            self.assertEqual(g.ftnc_absentes_du_suivi('9876543210'), ['VLB9876543210'])
            self.assertEqual(g.ftnc_absentes_du_suivi('1234567890'), [])

    def test_reference_without_ten_digits_does_not_crash(self):
        suivi = [{'reference': 'MWB1234567890', 'identifiant': '1234567890'}]
        df = pd.DataFrame({'ref': ['REF-COURTE', 'MWB1234567890']})
        with patch.object(g, '_lire_suivi', return_value=suivi), \
             patch.object(g, '_get_ftnc_config', return_value={
                 'fichier_ftnc': Path('x.xlsx'), 'feuille_ftnc': 'Feuille'}), \
             patch.object(g, '_verifier', return_value=Path('x.xlsx')), \
             patch.object(g.pd, 'read_excel', return_value=df):
            self.assertEqual(g.ftnc_absentes_du_suivi('REF-COURTE'), ['REF-COURTE'])
            self.assertEqual(g.ftnc_absentes_du_suivi('1234567890'), [])

    def test_missing_comparison_keeps_cards_and_exposes_error(self):
        turn = {}
        with patch.object(g, 'ftnc_cartes_suivi', return_value=[{'reference': 'X'}]), \
             patch.object(g, 'ftnc_absentes_du_suivi', side_effect=OSError('classeur indisponible')):
            load_ftnc_cards(turn, '', 'Liste')
        self.assertEqual(turn['ftnc_cards_data'], [{'reference': 'X'}])
        self.assertIn('classeur indisponible', turn['ftnc_missing_error'])


class EmptyResultTests(unittest.TestCase):
    def test_no_data_never_silently_blanks_turn(self):
        qt = types.ModuleType('PySide6')
        core = types.ModuleType('PySide6.QtCore')
        core.QTimer = type('QTimer', (), {'singleShot': staticmethod(lambda *args: None)})
        original = {name: sys.modules.get(name) for name in ('PySide6', 'PySide6.QtCore')}
        sys.modules.update({'PySide6': qt, 'PySide6.QtCore': core})
        try:
            path = Path(__file__).resolve().parents[1] / 'src/ui/windows/document_response_controller.py'
            spec = importlib.util.spec_from_file_location('ftnc_empty_controller', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            for name, old in original.items():
                if old is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = old
        dialog = types.SimpleNamespace(
            current_turn_index=0,
            turns=[{'answer': '', 'timeline': [], 'tools': [
                {'name': 'Liste', 'skill_name': 'FTNC', 'status': 'done', 'result': ''}]}],
            streaming_response_active=True,
            stream_render_timer=types.SimpleNamespace(stop=lambda: None),
            status=types.SimpleNamespace(clear=lambda: None, hide=lambda: None),
            stop_generation_button=types.SimpleNamespace(setEnabled=lambda _: None),
            _update_send_visibility=lambda: None,
            _render_conversation=lambda: None,
            _refresh_conversation_widths=lambda: None,
            MIN_HEIGHT=1,
        )
        module.DocumentResponseController(dialog).finish_response()
        self.assertIn('Aucun résultat', dialog.turns[0]['answer'])
        self.assertEqual(dialog.turns[0]['timeline'][-1]['type'], 'response')


if __name__ == '__main__':
    unittest.main()
