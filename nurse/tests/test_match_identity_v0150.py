"""Regresión MATCH: los brains UCI se identifican por ID, no por defaults Nurse."""
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
try:
    import chess
except ImportError:
    chess = types.ModuleType('chess')
    chess.__path__ = []
    chess.pgn = types.ModuleType('chess.pgn')
    sys.modules['chess'] = chess
    sys.modules['chess.pgn'] = chess.pgn

from nurse.match import match_side_identity


class MatchIdentityTests(unittest.TestCase):
    def setUp(self):
        self.args = SimpleNamespace(idA='dopey', idB='pico',
                                    a_player='sargon-plus', a_evaluator='classic',
                                    b_player='sargon-plus', b_evaluator='classic')

    def test_brain_ids_override_internal_defaults(self):
        self.assertEqual(match_side_identity(self.args, 'A'), 'dopey')
        self.assertEqual(match_side_identity(self.args, 'b'), 'pico')

    def test_without_brain_preserves_original_description(self):
        self.args.idA = None
        self.assertEqual(match_side_identity(self.args, 'A'), 'sargon-plus | classic')

    def test_invalid_side_is_rejected(self):
        with self.assertRaises(ValueError):
            match_side_identity(self.args, 'C')


if __name__ == '__main__':
    unittest.main()
