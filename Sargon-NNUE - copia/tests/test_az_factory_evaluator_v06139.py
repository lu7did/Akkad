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
#* test_az_factory_evaluator_v06139.py
#* Regression: AlphaZero preserves explicitly selected LC0/ZNPZ/ZCLASSIC evaluator.
#* v0.6.153
#=================================================================================================================*
"""Regression: AlphaZero preserves explicitly selected LC0/ZNPZ/ZCLASSIC evaluator.

Run: python -m unittest discover -s tests -p "test_az_factory_evaluator_v06139.py" -v
"""
import argparse
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from sargon_nnue.cli_common import add_engine_args
from sargon_nnue.factory import build_engine
from sargon_nnue.players.base import PlayerError


class AlphaZeroFactorySelectionTests(unittest.TestCase):
    def setUp(self):
        self.parser = argparse.ArgumentParser()
        add_engine_args(self.parser)

    def _check(self, kind):
        args = ['--player', 'alphazero', '--az-simulations', '3']
        if kind is not None:
            args.extend(['--evaluator', kind])
        if kind == 'znpz':
            args.extend(['--network', 'checkpoint-test.npz'])
        if kind in ('lc0', None):
            args.extend(['--lc0-weights', 'model-test.pb.gz'])
        captured = []

        def fake_evaluator(ev, *a, **kw):
            captured.append(ev)
            return SimpleNamespace(name=ev.upper(), network_id='test-network', history_mode='test-history')

        def fake_player(*a, **kw):
            return SimpleNamespace(name='ALPHAZERO')

        with patch('sargon_nnue.factory.create_evaluator', side_effect=fake_evaluator), \
             patch('sargon_nnue.factory.create_player', side_effect=fake_player):
            evaluator, player = build_engine(self.parser.parse_args(args))
        self.assertEqual(captured, [kind or 'lc0'])
        self.assertEqual(evaluator.name, (kind or 'lc0').upper())
        self.assertEqual(player.name, 'ALPHAZERO')

    def test_zclassic_explicit(self):
        self._check('zclassic')

    def test_znpz_explicit(self):
        self._check('znpz')

    def test_lc0_explicit(self):
        self._check('lc0')

    def test_lc0_default_when_omitted(self):
        self._check(None)

    def test_unsupported_evaluator_rejected(self):
        args = self.parser.parse_args(['--player', 'alphazero', '--evaluator', 'classic'])
        with self.assertRaises(PlayerError):
            build_engine(args)


if __name__ == '__main__':
    unittest.main()
