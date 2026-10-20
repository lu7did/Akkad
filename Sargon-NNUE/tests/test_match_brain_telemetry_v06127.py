#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_match_brain_telemetry_v06127.py
#* Pruebas sin dependencias externas para las etiquetas de sargon_match.py.
#* v0.6.153
#=================================================================================================================*
"""Pruebas sin dependencias externas para las etiquetas de sargon_match.py.

Evalua las asignaciones del codigo real mediante AST, sin reemplazar su logica
por una funcion duplicada dentro de la prueba.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

MATCH = Path(__file__).resolve().parents[1] / 'src' / 'sargon_nnue' / 'sargon_match.py'


def _identifiers(source, *, id_a, id_b):
    tree = ast.parse(source)
    wanted = {'player_labels', 'identity_a', 'identity_b'}
    matches = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for target in targets:
                if target in wanted:
                    matches[target] = node
    if set(matches) != wanted:
        raise AssertionError(f'Asignaciones faltantes: {wanted - set(matches)}')
    a = SimpleNamespace(
        idA=id_a, idB=id_b,
        a_player='sargon-plus', b_player='sargon-plus',
        a_evaluator='classic', b_evaluator='classic',
    )
    namespace = {'a': a}
    for name in ('player_labels', 'identity_a', 'identity_b'):
        statement = ast.fix_missing_locations(ast.Module(body=[matches[name]], type_ignores=[]))
        exec(compile(statement, str(MATCH), 'exec'), namespace)
    return namespace


class MatchBrainTelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MATCH.read_text(encoding='utf-8')

    def test_brain_ids_override_equal_player_evaluator(self):
        result = _identifiers(self.source, id_a='splus_d2', id_b='splus_d5')
        self.assertEqual(result['player_labels'], {'A': '(splus_d2)', 'B': '(splus_d5)'})
        self.assertEqual(result['identity_a'], 'splus_d2')
        self.assertEqual(result['identity_b'], 'splus_d5')

    def test_color_reversal_uses_correct_participant_id(self):
        labels = _identifiers(self.source, id_a='d2', id_b='d5')['player_labels']
        self.assertEqual((labels['A'], labels['B']), ('(d2)', '(d5)'))
        self.assertEqual((labels['B'], labels['A']), ('(d5)', '(d2)'))

    def test_no_brains_preserves_legacy_telemetry(self):
        result = _identifiers(self.source, id_a=None, id_b=None)
        self.assertEqual(result['player_labels'],
                         {'A': '(sargon-plus | classic)', 'B': '(sargon-plus | classic)'})
        self.assertEqual(result['identity_a'], 'sargon-plus | classic')
        self.assertEqual(result['identity_b'], 'sargon-plus | classic')

    def test_game_start_and_end_reuse_same_labels(self):
        self.assertIn('white_label=player_labels[white].ljust(label_width)', self.source)
        self.assertIn('black_label=player_labels[black].ljust(label_width)', self.source)
        self.assertIn("print(prefix + ' ♟️ -- ⏱️ --.-s (IN_PROGRESS)'", self.source)
        self.assertIn("print(prefix + f' ♟️ {board.ply():>3}", self.source)
        self.assertIn("f'({identity_a}) ({scores[\"A\"]:.1f} | {scores[\"B\"]:.1f}) '", self.source)


if __name__ == '__main__':
    unittest.main()
