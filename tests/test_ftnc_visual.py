"""Tests ciblés du rendu FTNC, sans PySide6 ni classeurs réels."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / 'src/ui/widgets/ftnc_card_parser.py'
spec = importlib.util.spec_from_file_location('ftnc_card_parser_test', PARSER)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
LIST = ('FTNC EN COURS\n' + '=' * 40 + '\n'
        '1. MWB1234567890 🚩 | ATL2 | En cours | Priorité : Urgent\n\n'
        'Nombre de FTNC du planner : 1\n\n'
        'NOUVELLES FTNC À AJOUTER AU PLANNER\n' + '-' * 40 + '\n'
        '2. [VLB1234567891] ATL2 - Support (REF-A) - 2 pièces\n'
        'Description vérifiée\nDate de début : 01/09/26\n\n'
        'Nombre de FTNC en cours dans le suivi €uro : 1')
DETAIL = ('DÉTAILS DE LA FTNC "MWB1234567890"\n' + '=' * 40 + '\n'
          'Source : FTNC.xlsx / planner\nRéférence FTNC : MWB1234567890\n'
          'Programme : ATL2\nStatut : En cours\nPriorité : Urgent')


class ParserTests(unittest.TestCase):
    def test_liste_and_quantity(self):
        self.assertEqual(parser.identify_ftnc_output(LIST), 'Liste')
        result = parser.parse_ftnc_result(LIST, 'Liste')
        self.assertEqual([len(s['cards']) for s in result['sections']], [1, 1])
        self.assertEqual(result['sections'][0]['cards'][0]['reference'], 'MWB1234567890')
        self.assertEqual(result['sections'][0]['cards'][0]['quantite'], '')
        self.assertEqual(result['sections'][1]['cards'][0]['quantite'], '2')
        self.assertEqual(len(result['counts']), 2)

    def test_details_and_fallback(self):
        self.assertEqual(parser.identify_ftnc_output(DETAIL), 'Details')
        self.assertEqual(parser.parse_ftnc_result(DETAIL, 'Details')['sections'][0]['cards'][0]['programme'], 'ATL2')
        self.assertEqual(parser.parse_ftnc_result('FTNC EN COURS\n1. invalide\nNombre de FTNC du planner : 1', 'Liste')['sections'], [])
        self.assertEqual(parser.identify_ftnc_output('Texte FTNC rédigé par un LLM'), '')

    def test_json_quoted_tool_output_becomes_cards(self):
        quoted = json.dumps(LIST, ensure_ascii=False)
        self.assertEqual(parser.normalize_ftnc_text(quoted), LIST)
        self.assertEqual(parser.identify_ftnc_output(quoted), 'Liste')
        cards = parser.parse_ftnc_result(quoted, 'Liste')['sections']
        self.assertEqual([len(section['cards']) for section in cards], [1, 1])

    def test_no_match(self):
        text = 'Aucune FTNC trouvée pour la référence "X".'
        self.assertEqual(parser.identify_ftnc_output(text), 'Details')
        self.assertEqual(parser.parse_ftnc_result(text, 'Details')['message'], text)


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        qt = types.ModuleType('PySide6')
        qtcore = types.ModuleType('PySide6.QtCore')
        qtcore.QTimer = type('QTimer', (), {'singleShot': staticmethod(lambda *args: None)})
        src = types.ModuleType('src')
        ui = types.ModuleType('src.ui')
        widgets = types.ModuleType('src.ui.widgets')
        old = {name: sys.modules.get(name) for name in
               ('PySide6', 'PySide6.QtCore', 'src', 'src.ui', 'src.ui.widgets',
                'src.ui.widgets.ftnc_card_parser')}
        sys.modules.update({'PySide6': qt, 'PySide6.QtCore': qtcore,
                            'src': src, 'src.ui': ui, 'src.ui.widgets': widgets,
                            'src.ui.widgets.ftnc_card_parser': parser})
        try:
            path = ROOT / 'src/ui/windows/document_response_controller.py'
            spec = importlib.util.spec_from_file_location('ftnc_controller_test', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.Controller = module.DocumentResponseController
        finally:
            for name, value in old.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value

    def _dialog(self, skill='FTNC', tag=None):
        dialog = types.SimpleNamespace()
        dialog.current_turn_index = 0
        dialog.turns = [{'timeline': [], 'answer': '', 'skill_tag': tag}]
        dialog.skill_manager = types.SimpleNamespace(
            get_tool=lambda name: {'skill': skill}, get_skill_icon=lambda name: None)
        dialog._render_conversation = lambda: None
        dialog.streaming_response_active = True
        dialog.current_thinking_widget = None
        dialog.stream_render_timer = types.SimpleNamespace(isActive=lambda: True, stop=lambda: None)
        return dialog

    def test_ftnc_event_case_insensitive(self):
        dialog = self._dialog()
        self.Controller(dialog).record_tool_event('résultat', 'Liste', LIST)
        self.assertEqual(dialog.turns[0]['ftnc_tool'], 'Liste')
        self.assertEqual(dialog.turns[0]['timeline'][-1]['type'], 'ftnc_visual')

    def test_quoted_event_result_becomes_cards(self):
        dialog = self._dialog()
        quoted = json.dumps(LIST, ensure_ascii=False)
        self.Controller(dialog).record_tool_event('appel', 'Liste', '{}')
        self.Controller(dialog).record_tool_event('résultat', 'Liste', quoted)
        self.assertEqual(dialog.turns[0]['ftnc_result'], LIST)
        self.assertEqual(dialog.turns[0]['timeline'][-1]['type'], 'ftnc_visual')
        self._prepare_finish(dialog)
        self.Controller(dialog).finish_response()
        self.assertNotIn('Aucun résultat', dialog.turns[0].get('answer', ''))
        self.assertEqual(dialog.turns[0]['timeline'][-1]['text'], LIST)

    def test_quoted_tool_result_recovered_at_finish(self):
        dialog = self._dialog(skill='')
        dialog.turns[0]['tools'] = [{'name': 'Liste', 'skill_name': '',
                                     'result': json.dumps(LIST, ensure_ascii=False),
                                     'status': 'done'}]
        self._prepare_finish(dialog)
        self.Controller(dialog).finish_response()
        self.assertEqual(dialog.turns[0]['ftnc_result'], LIST)

    def test_ftnc_local_not_intercepted(self):
        dialog = self._dialog(skill='ftnc_local')
        self.Controller(dialog).record_tool_event('résultat', 'Liste', LIST)
        self.assertNotIn('ftnc_result', dialog.turns[0])

    def test_ftnc_local_direct_answer_not_intercepted(self):
        dialog = self._dialog(skill='ftnc_local')
        dialog.turns[0]['answer'] = DETAIL
        dialog.turns[0]['tools'] = [{'skill_name': 'ftnc_local', 'status': 'done'}]
        dialog.stream_render_timer = types.SimpleNamespace(stop=lambda: None)
        dialog.status = types.SimpleNamespace(clear=lambda: None, hide=lambda: None)
        dialog.stop_generation_button = types.SimpleNamespace(setEnabled=lambda _: None)
        dialog._update_send_visibility = lambda: None
        dialog._refresh_conversation_widths = lambda: None
        dialog.MIN_HEIGHT = 1
        self.Controller(dialog).finish_response()
        self.assertNotIn('ftnc_result', dialog.turns[0])
        self.assertEqual(dialog.turns[0]['answer'], DETAIL)

    def _prepare_finish(self, dialog):
        dialog.stream_render_timer = types.SimpleNamespace(stop=lambda: None)
        dialog.status = types.SimpleNamespace(clear=lambda: None, hide=lambda: None)
        dialog.stop_generation_button = types.SimpleNamespace(setEnabled=lambda _: None)
        dialog._update_send_visibility = lambda: None
        dialog._refresh_conversation_widths = lambda: None
        dialog.MIN_HEIGHT = 1

    def test_empty_result_uses_final_answer_instead_of_blank(self):
        dialog = self._dialog()
        self.Controller(dialog).record_tool_event('appel', 'Liste', '')
        self.Controller(dialog).record_tool_event('résultat', 'Liste', '')
        self.assertNotIn('ftnc_result', dialog.turns[0])
        self.Controller(dialog).append_response(LIST)
        self._prepare_finish(dialog)
        self.Controller(dialog).finish_response()
        self.assertEqual(dialog.turns[0]['ftnc_tool'], 'Liste')
        self.assertEqual(dialog.turns[0]['timeline'][-1]['type'], 'ftnc_visual')
        self.assertEqual(dialog.turns[0]['timeline'][-1]['text'], LIST)

    def test_no_final_answer_uses_tool_result(self):
        dialog = self._dialog()
        self.Controller(dialog).record_tool_event('appel', 'Liste', '')
        dialog.turns[0]['tools'][0]['result'] = LIST
        self._prepare_finish(dialog)
        self.Controller(dialog).finish_response()
        self.assertEqual(dialog.turns[0]['ftnc_result'], LIST)

    def test_no_data_never_silently_blanks_turn(self):
        dialog = self._dialog()
        self.Controller(dialog).record_tool_event('appel', 'Liste', '')
        self._prepare_finish(dialog)
        self.Controller(dialog).finish_response()
        self.assertIn('Aucun résultat', dialog.turns[0]['answer'])

    def test_alias_and_direct_answer(self):
        dialog = self._dialog(skill='other')
        self.Controller(dialog).record_tool_event('résultat', 'ftnc_liste', LIST)
        self.assertEqual(dialog.turns[0]['ftnc_tool'], 'Liste')
        dialog = self._dialog(skill='FTNC')
        dialog.turns[0]['answer'] = DETAIL
        dialog.turns[0]['timeline'] = [{'type': 'response', 'text': DETAIL}]
        dialog.stream_render_timer = types.SimpleNamespace(stop=lambda: None)
        dialog.status = types.SimpleNamespace(clear=lambda: None, hide=lambda: None)
        dialog.stop_generation_button = types.SimpleNamespace(setEnabled=lambda _: None)
        dialog._update_send_visibility = lambda: None
        dialog._refresh_conversation_widths = lambda: None
        dialog._allow_shrink_height = False
        dialog.MIN_HEIGHT = 1
        dialog._render_conversation = lambda: None
        self.Controller(dialog).finish_response()
        self.assertEqual(dialog.turns[0]['answer'], '')
        self.assertEqual(dialog.turns[0]['ftnc_tool'], 'Details')
        self.assertEqual(dialog.turns[0]['timeline'][-1]['type'], 'ftnc_visual')


if __name__ == '__main__':
    unittest.main()
