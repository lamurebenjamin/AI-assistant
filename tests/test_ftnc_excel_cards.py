"""Tests du contenu Excel et de l'indicateur planner des cartes FTNC."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from skills.ftnc import generator as g
from src.ui.widgets.ftnc_card_data import load_ftnc_cards
from src.ui.widgets.ftnc_card_parser import (
    ftnc_reference_from_output,
    identify_ftnc_output,
    normalize_ftnc_text,
    parse_ftnc_result,
)


class FtncExcelCardTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                'reference': 'MWB1234567890', 'numero': '1234567890', 'identifiant': '1234567890',
                'programme': 'ATL2', 'quantite': '2', 'statut': 'En cours', 'type': 'Structure',
                'pole': 'PPM', 'designation': 'Support', 'reference_piece': 'A',
                'date_debut': '01/09/26', 'description': 'Première',
            },
            {
                'reference': 'VLB9876543210', 'numero': '9876543210', 'identifiant': '9876543210',
                'programme': 'ATL2', 'quantite': '3', 'statut': 'En cours', 'type': 'Carbone',
                'pole': 'PPM', 'designation': 'Renfort', 'reference_piece': 'B',
                'date_debut': '02/09/26', 'description': 'Seconde',
            },
        ]

    def test_cards_only_suivi_and_planner_icon_flag(self):
        with patch.object(g, '_lire_suivi', return_value=self.rows), patch.object(
                g, '_references_planner_pour_cartes', return_value=({'1234567890'}, {'mwb1234567890'})):
            cards = g.ftnc_cartes_suivi()
            self.assertEqual(len(cards), 2)
            self.assertEqual([c['sur_planner'] for c in cards], [True, False])
            self.assertEqual([c['quantite'] for c in cards], ['2', '3'])
            self.assertNotIn('priorite', cards[0])
            self.assertNotIn('ligne_excel', cards[0])
            self.assertEqual(g.ftnc_cartes_suivi('9876543210')[0]['reference'], 'VLB9876543210')

    def test_planner_presence_reads_all_column_b_references(self):
        df = pd.DataFrame({'Référence': ['MWB1234567890', 'REF-SANS-DIX-CHIFFRES', None]})
        with patch.object(g, '_get_ftnc_config', return_value={
            'fichier_ftnc': Path('/tmp/FTNC.xlsx'), 'feuille_ftnc': 'Données consolidées'}),              patch.object(g, '_verifier', return_value=Path('/tmp/FTNC.xlsx')),              patch.object(g.pd, 'read_excel', return_value=df) as reader:
            ids, refs = g._references_planner_pour_cartes()
            self.assertIn('1234567890', ids)
            self.assertIn('refsansdixchiffres', refs)
            self.assertEqual(reader.call_args.kwargs['usecols'], 'B')

    def test_quoted_result_and_old_parser_contract(self):
        text = ('FTNC EN COURS\n' + '=' * 40 + '\n'
                '1. MWB1234567890 🚩 | ATL2 | En cours | Priorité : Urgent\n\n'
                'Nombre de FTNC du planner : 1\n\n'
                'NOUVELLES FTNC À AJOUTER AU PLANNER\n' + '-' * 40 + '\n'
                '2. [VLB9876543210] ATL2 - Renfort (B) - 3 pièces\n'
                'Seconde\nDate de début : 02/09/26\n\n'
                'Nombre de FTNC en cours dans le suivi €uro : 2')
        quoted = json.dumps(text, ensure_ascii=False)
        self.assertEqual(identify_ftnc_output(quoted), 'Liste')
        self.assertEqual(normalize_ftnc_text(quoted), text)
        sections = parse_ftnc_result(quoted, 'Liste')['sections']
        self.assertEqual([len(s['cards']) for s in sections], [1, 1])
        self.assertEqual(sections[0]['cards'][0]['quantite'], '')
        self.assertEqual(sections[1]['cards'][0]['quantite'], '3')
        self.assertEqual(ftnc_reference_from_output('DÉTAILS DE LA FTNC "VLB9876543210"\nSource : X'),
                         'VLB9876543210')

    def test_load_once_and_details_filter(self):
        turn = {}
        with patch.object(g, 'ftnc_cartes_suivi', return_value=[{'reference': 'X'}]) as loader:
            load_ftnc_cards(turn, 'DÉTAILS DE LA FTNC "X"\nSource : S', 'Details')
            load_ftnc_cards(turn, 'DÉTAILS DE LA FTNC "X"\nSource : S', 'Details')
            loader.assert_called_once_with('X')
            self.assertEqual(turn['ftnc_cards_data'], [{'reference': 'X'}])

    def test_width_contract_and_svg_location(self):
        source = (Path(__file__).resolve().parents[1] /
                  'src/ui/widgets/ftnc_cards_widget.py').read_text(encoding='utf-8')
        self.assertIn('CARD_MAX_WIDTH = 180', source)
        self.assertIn("'skills' / 'ftnc' / 'planner.svg'", source)
        self.assertIn('def resizeEvent(', source)
        self.assertIn('QGridLayout', source)


class FtncRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        qt = types.ModuleType('PySide6')
        core = types.ModuleType('PySide6.QtCore')
        core.QTimer = type('QTimer', (), {'singleShot': staticmethod(lambda *args: None)})
        names = ('PySide6', 'PySide6.QtCore')
        old = {name: sys.modules.get(name) for name in names}
        sys.modules.update({'PySide6': qt, 'PySide6.QtCore': core})
        try:
            source = (Path(__file__).resolve().parents[1] /
                      'src/ui/windows/document_response_controller.py')
            spec = importlib.util.spec_from_file_location('ftnc_controller_grid_test', source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.Controller = module.DocumentResponseController
        finally:
            for name, value in old.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value

    def test_event_attaches_excel_cards(self):
        turn = {'timeline': [], 'answer': '', 'skill_tag': 'FTNC'}
        dialog = types.SimpleNamespace(current_turn_index=0, turns=[turn],
            skill_manager=types.SimpleNamespace(get_tool=lambda _: {'skill': 'FTNC'},
                                                get_skill_icon=lambda _: None),
            _render_conversation=lambda: None, streaming_response_active=True)
        text = 'FTNC EN COURS\n' + '=' * 40 + '\nNombre de FTNC du planner : 0'
        with patch.object(g, 'ftnc_cartes_suivi', return_value=[{'reference': 'REF', 'sur_planner': True}]):
            self.Controller(dialog).record_tool_event('résultat', 'Liste', json.dumps(text))
        self.assertEqual(turn['ftnc_cards_data'][0]['reference'], 'REF')
        self.assertEqual(turn['timeline'][-1]['type'], 'ftnc_visual')

    def test_local_tool_not_intercepted(self):
        turn = {'timeline': [], 'answer': ''}
        dialog = types.SimpleNamespace(current_turn_index=0, turns=[turn],
            skill_manager=types.SimpleNamespace(get_tool=lambda _: {'skill': 'ftnc_local'},
                                                get_skill_icon=lambda _: None),
            _render_conversation=lambda: None)
        text = 'FTNC EN COURS\n' + '=' * 40 + '\nNombre de FTNC du planner : 0'
        self.Controller(dialog).record_tool_event('résultat', 'Liste', text)
        self.assertNotIn('ftnc_cards_data', turn)


if __name__ == '__main__':
    unittest.main()
