"""picoGen v0.1.43: output bias calibration without chess dependency."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gen_nnue_evolution import PARAMS


def load_calibration():
    dummy_dataset = types.ModuleType('gen_csv_dataset')
    dummy_dataset.load_pair = lambda *a: None
    dummy_core = types.ModuleType('gen_fp32_core')
    for key in ('padded_features', 'nnue_forward', 'write_json_atomic', 'write_npy_atomic'):
        setattr(dummy_core, key, lambda *a: None)
    with patch.dict(sys.modules, {'gen_csv_dataset':dummy_dataset,'gen_fp32_core':dummy_core}):
        spec = importlib.util.spec_from_file_location('calibration_v143', ROOT/'genNNUE.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module.calibrate_output_bias


class BiasCalibrationTests(unittest.TestCase):
    def test_mean_signed_error_is_removed(self):
        calibrate = load_calibration()
        genes = np.zeros(PARAMS, dtype=np.float32)
        genes[-1] = 100.0
        predicted = np.array([110.0, 90.0, 130.0, 70.0])
        targets = np.array([10.0, -10.0, 30.0, -30.0])
        mse, delta, post_mean = calibrate(genes, predicted, targets)
        self.assertEqual(delta, -100.0)
        self.assertEqual(float(genes[-1]), 0.0)
        self.assertEqual(mse, 0.0)
        self.assertEqual(post_mean, 0.0)

    def test_mse_minimizer_preserves_variance(self):
        calibrate = load_calibration()
        genes = np.zeros(PARAMS, dtype=np.float32)
        prediction = np.array([100.0, 200.0, 300.0])
        targets = np.array([80.0, 100.0, 220.0])
        old = np.mean((prediction-targets)**2)
        mse, delta, signed = calibrate(genes, prediction, targets)
        self.assertAlmostEqual(signed, 0.0, places=4)
        self.assertLess(mse, old)
        self.assertAlmostEqual(mse, np.var(prediction-targets), delta=1e-3)
        self.assertEqual(genes.dtype, np.float32)

    def test_cannot_use_invalid_chromosome(self):
        calibrate = load_calibration()
        with self.assertRaises(ValueError):
            calibrate(np.zeros(PARAMS, dtype=np.int16), [1.0], [0.0])
        with self.assertRaises(ValueError):
            calibrate(np.zeros(PARAMS, dtype=np.float32), [np.nan], [0.0])

if __name__ == '__main__':unittest.main()
