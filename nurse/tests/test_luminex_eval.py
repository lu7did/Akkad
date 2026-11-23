"""Contract tests for LNNUE v1 parser, output normalization, and Nurse registration."""
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from nurse.luminex_eval import LuminexEvaluator, EXPECTED_SIZE
from nurse.engine_registry import ensure_pair, source



def binary(*, output_bias=0, output_weight=0, bad_header=False):
    hdr = struct.pack('<5s5i', b'BAD!!' if bad_header else b'LNNUE', 1, 768, 32, 255, 64)
    w = [0] * (768 * 32)
    b = [0] * 32
    o = [0] * 32
    o[0] = output_weight
    return hdr + struct.pack('<' + 'h' * (len(w)+len(b)+len(o)+1), *(w+b+o+[output_bias]))


class LuminexTests(unittest.TestCase):
    def test_header_size_and_probability_to_cp(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'net.bin'
            p.write_bytes(binary())
            self.assertEqual(p.stat().st_size, EXPECTED_SIZE)
            ev = LuminexEvaluator(str(p))
            ev.active_features = lambda board: (0, 63, 511)
            self.assertEqual(ev.evaluate(None), 0)
            p.write_bytes(binary(output_bias=64))
            ev = LuminexEvaluator(str(p))
            ev.active_features = lambda board: (0, 63, 511)
            self.assertEqual(ev.evaluate(None), 200)
            p.write_bytes(binary(output_bias=-64))
            ev = LuminexEvaluator(str(p))
            ev.active_features = lambda board: (0, 63, 511)
            self.assertEqual(ev.evaluate(None), -200)

    def test_reject_wrong_format_and_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'net.bin'
            p.write_bytes(binary(bad_header=True))
            with self.assertRaisesRegex(Exception, 'cabecera'):LuminexEvaluator(str(p))
            p.write_bytes(binary()[:-1])
            with self.assertRaisesRegex(Exception, 'tamaño'):LuminexEvaluator(str(p))

    def test_registry_and_brain_for_ordinary_players(self):
        ensure_pair('sargon','luminex',nurse_only=True)
        ensure_pair('sargon-plus','luminex',nurse_only=True)
        with self.assertRaisesRegex(ValueError,'incompatible'):
            ensure_pair('mctsp','luminex',nurse_only=True)
        self.assertTrue(Path(source('evaluator','luminex')).is_file())
        try:
            from nurse.config import read_brain
        except ImportError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'luminex-nnue-32.bin';p.write_bytes(binary())
            brains = Path(folder)/'brains.json'
            brains.write_text(json.dumps({'brains':{'test':{'type':'nurse','player':'sargon-plus',
                'evaluator':{'evaluator':'luminex','network':p.name}}}}))
            cfg=read_brain(str(brains),'test')
            self.assertEqual(cfg['_evaluator'],'luminex')

if __name__ == '__main__':unittest.main()
