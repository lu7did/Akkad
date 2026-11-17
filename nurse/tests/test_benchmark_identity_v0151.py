"""Regression checks for benchmark transport-aware headings.

Run: python -m unittest discover -s nurse/tests -p 'test_benchmark_identity_v0151.py' -v
"""
import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'src' / 'nurse' / 'display.py'
spec = importlib.util.spec_from_file_location('nurse_display_under_test', MODULE)
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)


class BenchmarkIdentityTests(unittest.TestCase):
    def test_uci_uses_brain_id_executable_and_weights(self):
        cfg = {
            'type': 'uci', 'player': 'picoSargon', 'evaluator': 'null',
            '_engine': r'C:\akkad\picoSargon\x86\build\picoSargon.exe',
            '_args': ['--weights', r'C:\akkad\picoSargon\assets\dopey.bin', '--depth', '4'],
        }
        heading = display.benchmark_engine_heading('dopey', cfg)
        self.assertEqual(heading, 'dopey (UCI | picoSargon.exe | pesos=dopey.bin)')
        self.assertNotIn('default', heading)
        self.assertNotIn('sargon-plus', heading)

    def test_separate_brains_same_executable_have_different_weight_labels(self):
        cfg = {'type': 'uci', '_engine': '/bin/picoSargon', 'player': 'picoSargon',
               '_args': ['--weights', '/assets/grumpy.bin']}
        self.assertEqual(display.benchmark_engine_heading('pico', cfg),
                         'pico (UCI | picoSargon | pesos=grumpy.bin)')

    def test_uci_without_weights_does_not_fabricate_any(self):
        cfg = {'type': 'uci', 'player': 'stockfish', '_engine': '/usr/bin/stockfish', '_args': []}
        self.assertEqual(display.benchmark_engine_heading('fishy', cfg),
                         'fishy (UCI | stockfish)')

    def test_nurse_shows_internal_player_evaluator(self):
        cfg = {'type': 'nurse', 'player': 'mctsp', 'evaluator': 'mctse'}
        self.assertEqual(display.benchmark_engine_heading('dalia', cfg),
                         'dalia (Nurse | mctsp | mctse)')

    def test_external_preserves_brain_id_and_remote_name(self):
        cfg = {'type': 'external', 'player': 'external', 'evaluator': 'null'}
        self.assertEqual(display.benchmark_engine_heading('pixie', cfg, 'picoPixie UCI'),
                         'pixie (TCP | picoPixie UCI)')


if __name__ == '__main__':
    unittest.main()
