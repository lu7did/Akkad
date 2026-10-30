"""Integration smoke checks. Run: python -m unittest discover -s tests -p 'test_picokeras_integration_v06184.py'"""
import argparse
import unittest

from sargon_nnue import brains
from sargon_nnue.cli_common import add_engine_args


class PicoKerasProfileTest(unittest.TestCase):
    def test_brain_with_binary_and_network(self):
        config = {
            'player': 'picoKeras', 'evaluator': 'null',
            'engine-path': '../x86/picoKeras/build/Release/picoKeras.exe',
            'network': '../data/runs/keras/small.int8.tflite',
            'timeout': 30000, 'rating_elo': 400,
        }
        self.assertEqual(brains.validate(config)['player'], 'picoKeras')
        ns = brains.engine_parser().parse_args(brains.to_argv(config))
        self.assertEqual(ns.player, 'picoKeras')
        self.assertEqual(ns.evaluator, 'null')
        self.assertEqual(ns.network, config['network'])

    def test_invalid_evaluator(self):
        with self.assertRaises(ValueError):
            brains.validate({'player':'picokeras','evaluator':'classic', 'engine-path':'a', 'network':'b'})

    def test_required_network_and_exe(self):
        for missing in ('engine-path', 'network'):
            cfg={'player':'picokeras','evaluator':'null', 'engine-path':'a', 'network':'b'}
            del cfg[missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                brains.validate(cfg)

    def test_prefixed_match_parser(self):
        p=argparse.ArgumentParser()
        add_engine_args(p,prefix='a_')
        ns=p.parse_args(['--a-player','picokeras','--a-evaluator','null', '--a-network','small.int8.tflite'])
        self.assertEqual(ns.a_player,'picokeras')


if __name__ == '__main__':
    unittest.main()
