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
#* test_brainmaker_level_v06148.py
#* Ejecuta pruebas de regresion para test brainmaker level v06148
#* v0.6.153
#=================================================================================================================*
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from sargon_nnue.sargon_brainmaker import level_report

class LevelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.brain = root / 'brains.json'
        self.rally = root / 'rally.json'
        self.brain.write_text(json.dumps({'brains': {
            'a': {'rating_elo': 1000, 'player': 'stockfish', 'evaluator': 'null'},
            'b': {'rating_elo': 1000, 'player': 'sargon', 'evaluator': 'classic'},
            'c': {'rating_elo': 1200, 'player': 'sargon', 'evaluator': 'classic'},
        }}), encoding='utf-8')
        self.rows = [
            {'match': 1, 'game': 1, 'white': 'a', 'black': 'b', 'result': '1-0'},
            {'match': 1, 'game': 2, 'white': 'b', 'black': 'a', 'result': '1/2-1/2'},
            {'match': 2, 'game': 1, 'white': 'a', 'black': 'c', 'result': '*'},
        ]
        self.write_rows()

    def tearDown(self):
        self.tmp.cleanup()

    def write_rows(self):
        self.rally.write_text(json.dumps({'tournaments': {'t': {'ranking': {'resultados': self.rows}}}}), encoding='utf-8')

    def run_report(self, save=False, k=32):
        with contextlib.redirect_stdout(io.StringIO()):
            return level_report(self.brain, self.rally, k, save)

    def test_no_save_and_incomplete_skipped(self):
        old = self.brain.read_bytes()
        self.assertEqual(self.run_report(), 0)
        self.assertEqual(old, self.brain.read_bytes())

    def test_save_zero_sum_and_unplayed_unchanged(self):
        self.run_report(True)
        r = json.loads(self.brain.read_text())['brains']
        self.assertEqual(r['a']['rating_elo'], 1016)
        self.assertEqual(r['b']['rating_elo'], 984)
        self.assertEqual(r['c']['rating_elo'], 1200)
        self.assertEqual(r['a']['player'], 'stockfish')

    def test_order_independent(self):
        self.rows.reverse()
        self.write_rows()
        self.run_report(True)
        r = json.loads(self.brain.read_text())['brains']
        self.assertEqual(r['a']['rating_elo'], 1016)

    def test_duplicate_detection(self):
        self.rows.append(dict(self.rows[0]))
        self.write_rows()
        with self.assertRaisesRegex(ValueError, 'duplicado'):
            self.run_report()

    def test_missing_rating_defaults_400(self):
        b = json.loads(self.brain.read_text())
        del b['brains']['a']['rating_elo']
        self.brain.write_text(json.dumps(b))
        original = self.brain.read_bytes()
        self.run_report()
        self.assertEqual(self.brain.read_bytes(), original)
        self.run_report(True)
        r = json.loads(self.brain.read_text())['brains']
        self.assertGreater(r['a']['rating_elo'], 400)
        self.assertLess(r['b']['rating_elo'], 1000)

    def test_unplayed_missing_rating_persists_400(self):
        b = json.loads(self.brain.read_text())
        del b['brains']['c']['rating_elo']
        self.brain.write_text(json.dumps(b))
        self.run_report(True)
        r = json.loads(self.brain.read_text())['brains']
        self.assertEqual(r['c']['rating_elo'], 400)

    def test_explicit_invalid_rating_rejected(self):
        b = json.loads(self.brain.read_text())
        b['brains']['a']['rating_elo'] = 'bad'
        self.brain.write_text(json.dumps(b))
        with self.assertRaisesRegex(ValueError, 'rating_elo inicial inválido'):
            self.run_report()

    def test_missing_brain(self):
        self.rows[0]['black'] = 'unknown'
        self.write_rows()
        with self.assertRaisesRegex(ValueError, 'brain ausente'):
            self.run_report()

if __name__ == '__main__':
    unittest.main()
