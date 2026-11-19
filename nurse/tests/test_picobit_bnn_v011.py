"""Nurse BNN registry regression after migration to Bullet BULBNN01 (v0.1.37).

Historical filename retained because this test was part of Nurse's test suite;
picoBit remains available independently in picoBit/src/bnn.py.
"""
from pathlib import Path
import sys
import unittest

NURSE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NURSE_ROOT / 'src'))

try:
    from nurse import engine_registry
    from nurse.bnn_eval import _implementation, make_bnn
    import chess
except ImportError as e:
    raise unittest.SkipTest(f'Falta dependencia de ejecución Nurse: {e}')

class BNNRegistryTest(unittest.TestCase):
    def test_registry(self):
        self.assertIn('bnn', engine_registry.choices('evaluator'))
        for player in ('sargon', 'sargon-plus', 'doc'):
            engine_registry.ensure_pair(player, 'bnn', nurse_only=True)

    def test_new_implementation(self):
        self.assertEqual(_implementation().MAGIC, b'BULBNN01')

    def test_factory_requires_network(self):
        with self.assertRaisesRegex(ValueError, 'network'):
            make_bnn()

    def test_legacy_creator_calls_factory(self):
        from unittest.mock import patch
        from nurse._legacy.evaluators import create_evaluator
        with patch('nurse.bnn_eval.make_bnn') as mocked:
            self.assertIs(create_evaluator('bnn', 'model.bnn'), mocked.return_value)
            self.assertEqual(mocked.call_args.kwargs['network'], 'model.bnn')

if __name__ == '__main__':
    unittest.main()
