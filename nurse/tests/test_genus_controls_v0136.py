"""Regression: every Nurse CLI and validation entrypoint accepts the GENUS evaluators.

Run: python -m unittest discover -s nurse/tests -p test_genus_controls_v0136.py -v
"""
import argparse
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    import chess
except ImportError:
    chess = types.ModuleType('chess')
    chess.__path__ = []
    chess.pgn = types.ModuleType('chess.pgn')
    sys.modules['chess'] = chess
    sys.modules['chess.pgn'] = chess.pgn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nurse._legacy.brains import EVALUATOR_CHOICES, defaults, validate
from nurse._legacy.cli_common import add_engine_args
from nurse.config import EVALUATORS, read_brain
from nurse import match

class TestGenusControls(unittest.TestCase):
    def test_match_flags_both_sides(self):
        parser=argparse.ArgumentParser()
        match.add_side(parser,'a')
        match.add_side(parser,'b')
        args=parser.parse_args(['--a-player','sargon-plus','--a-evaluator','genus-pst',
                                '--a-network','some/path/pst.json',
                                '--b-player','sargon','--b-evaluator','genus-nnue',
                                '--b-network','some/path/nnue.npy'])
        self.assertEqual(args.a_evaluator,'genus-pst')
        self.assertEqual(args.b_evaluator,'genus-nnue')

    def test_engine_parser_and_brainmaker_choices(self):
        parser=argparse.ArgumentParser()
        add_engine_args(parser)
        for ev in ('genus-pst','genus-nnue'):
            self.assertIn(ev,EVALUATOR_CHOICES)
            self.assertIn(ev,EVALUATORS)
            self.assertEqual(parser.parse_args(['--player','sargon-plus',
                                                '--evaluator',ev,'--network','weights']) .evaluator,ev)
            self.assertEqual(defaults('sargon-plus',ev)['evaluator'],ev)
            self.assertIn('network',defaults('sargon-plus',ev))

    def test_legacy_brain_validation(self):
        for ev in ('genus-pst','genus-nnue'):
            cfg={'player':'sargon-plus','evaluator':ev,'network':'models/model'}
            self.assertEqual(validate(cfg)['evaluator'],ev)
            with self.assertRaisesRegex(ValueError,'requiere network'):
                validate({'player':'sargon-plus','evaluator':ev})

    def test_nurse_brains_config(self):
        for ev in ('genus-pst','genus-nnue'):
            with tempfile.TemporaryDirectory() as d:
                cfg=Path(d)/'brains.json'
                (Path(d)/'weights.file').write_bytes(b'test-model-path')
                cfg.write_text(json.dumps({'brains':{'x':{'type':'nurse','player':'sargon-plus',
                    'evaluator':{'evaluator':ev,'network':'weights.file'},
                    'Depth':3,'QDepth':2,'tmax':15000,'timeout':30000}}}))
                parsed=read_brain(str(cfg),'x')
                self.assertEqual(parsed['_evaluator'],ev)
                self.assertEqual(parsed['_player'],'sargon-plus')

if __name__=='__main__':unittest.main()
