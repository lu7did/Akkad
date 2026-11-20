"""End-to-end FP32 GENUS model loading and pure NumPy inference checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from nurse.genus_eval import GenusEvaluator, resolve_active
from nurse._genus_core import nnue as nnue_core


class FakePST:
    DEFAULTS = {'PAWN_VALUE': 100, 'KNIGHT_VALUE': 310}
    SPECS = [('KNIGHT_VALUE', 11, 0, 2047)]
    @staticmethod
    def evaluate(_board, params):
        return params['KNIGHT_VALUE'] - 100


class GenusFP32Tests(unittest.TestCase):
    def test_fp32_pst(self):
        with tempfile.TemporaryDirectory() as td, patch('nurse.genus_eval.pst_core', FakePST):
            p = Path(td) / 'best.json'
            p.write_text(json.dumps({'format': 'picogen-binpack-genetic-fp32-v1',
                                     'dtype': 'float32', 'model': 'PST',
                                     'parameters': {'PAWN_VALUE': 100.0, 'KNIGHT_VALUE': 314.25}}))
            e = GenusEvaluator('pst', coefficient=str(p))
            self.assertEqual(e.evaluate(None), 214)
            self.assertEqual(e.coefficients['KNIGHT_VALUE'], 314.25)

    def test_fp32_nnue_active_and_prediction(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'best.npy'
            w = np.zeros(nnue_core.PARAMS, dtype=np.float32)
            w[0:nnue_core.HIDDEN] = np.float32(0.125)
            w[nnue_core.INPUTS * nnue_core.HIDDEN + nnue_core.HIDDEN] = np.float32(3.5)
            w[-1] = np.float32(0.25)
            np.save(p, w)
            p.with_name('best.active.json').write_text(json.dumps({
                'format': 'picogen-nnue-active-fp32-v1', 'dtype': 'float32',
                'file': 'best.npy', 'generation': 1, 'genes': nnue_core.PARAMS,
                'output_scale': 1}))
            e = GenusEvaluator('nnue', network=str(p))
            self.assertEqual(e.network_weights.dtype, np.dtype('float32'))
            self.assertFalse(e.network_weights.flags.writeable)
            x = np.zeros((1, 32), dtype=np.int32)
            mask = np.zeros((1, 32), dtype=np.int64)
            mask[0, 0] = 1
            score = nnue_core.forward(e.network_weights, x, mask)[0]
            self.assertAlmostEqual(float(score), 0.6875, places=5)

    def test_integer_backward_compatibility(self):
        x = np.zeros((1, 32), dtype=np.int32)
        mask = np.zeros((1, 32), dtype=np.int64); mask[0, 0] = 1
        for dt, expected in ((np.int16, 6.0), (np.int8, 6.0 / 256)):
            w = np.zeros(nnue_core.PARAMS, dtype=dt)
            w[0] = 2
            w[nnue_core.INPUTS * nnue_core.HIDDEN + nnue_core.HIDDEN] = 3
            self.assertAlmostEqual(float(nnue_core.forward(w, x, mask)[0]), expected)

    def test_nonfinite_and_wrong_dtype_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'best.npy'
            w = np.zeros(nnue_core.PARAMS, dtype=np.float32); w[0] = np.nan
            np.save(p, w)
            with self.assertRaisesRegex(ValueError, 'nonfinite'):
                GenusEvaluator('nnue', network=str(p))
            np.save(p, np.zeros(nnue_core.PARAMS, dtype=np.float64))
            with self.assertRaisesRegex(ValueError, 'incompatible model'):
                GenusEvaluator('nnue', network=str(p))

    def test_active_path_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'best.npy'; np.save(p, np.zeros(nnue_core.PARAMS, np.float32))
            p.with_name('best.active.json').write_text(json.dumps({
                'format': 'picogen-nnue-active-fp32-v1', 'dtype': 'float32',
                'file': '../model.npy', 'genes': nnue_core.PARAMS, 'output_scale': 1}))
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                resolve_active(p)

if __name__ == '__main__': unittest.main()
