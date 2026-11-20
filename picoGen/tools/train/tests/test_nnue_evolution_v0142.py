"""Contract tests: fp32, coherent hidden-unit crossover, sigma, immigrants, replay."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gen_nnue_evolution import (INPUTS, HIDDEN, PARAMS, ELITES, initial, breed,
                                cross_neurons, adaptive_sigma, success_count)


class EvolutionTests(unittest.TestCase):
    def test_full_hidden_units(self):
        a = np.full(PARAMS, 11.0, dtype=np.float32)
        b = np.full(PARAMS, -17.0, dtype=np.float32)
        rng = np.random.default_rng(42)
        child = cross_neurons(a, b, rng)
        weights = child[:INPUTS * HIDDEN].reshape(INPUTS, HIDDEN)
        biases = child[INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN]
        output = child[INPUTS * HIDDEN + HIDDEN:-1]
        self.assertTrue(set(np.unique(weights)).issubset({11., -17.}))
        self.assertIn(11., np.unique(biases))
        self.assertIn(-17., np.unique(biases))
        for j in range(HIDDEN):
            self.assertTrue(np.all(weights[:, j] == biases[j]))
            self.assertEqual(biases[j], output[j])

    def test_sigma_controller(self):
        self.assertAlmostEqual(adaptive_sigma(5.0, 12, 40), 5.5)
        self.assertAlmostEqual(adaptive_sigma(5.0, 5, 40), 4.5)
        self.assertEqual(adaptive_sigma(0.1, 0, 40), 0.1)
        self.assertEqual(adaptive_sigma(20., 40, 40), 20.)
        self.assertEqual(success_count([3., 7., 1.], [4., np.nan, 0.]), (1, 2))

    def test_immigrants_and_elites(self):
        rng = np.random.default_rng(7)
        pop = initial(rng, 50)
        mse = np.arange(50., 0., -1.)
        result, baseline, info = breed(pop, mse, rng, 5., restart=True)
        self.assertEqual(result.dtype, np.float32)
        self.assertEqual(result.shape, (50, PARAMS))
        self.assertEqual(info['immigrants'], 9)
        np.testing.assert_array_equal(result[:ELITES], pop[np.argsort(mse)[:ELITES]])
        self.assertTrue(np.isnan(baseline[:ELITES]).all())
        self.assertTrue(np.isfinite(baseline[ELITES:]).all())

    def test_checkpoint_resume_reproduces_population(self):
        rng = np.random.default_rng(4)
        pop = initial(rng, 8)
        fit = np.arange(8., dtype=np.float64)
        saved = rng.bit_generator.state
        next_a, base_a, _ = breed(pop, fit, rng, 4.5, restart=True)
        same_rng = np.random.default_rng(123)
        same_rng.bit_generator.state = saved
        next_b, base_b, _ = breed(pop, fit, same_rng, 4.5, restart=True)
        np.testing.assert_array_equal(next_a, next_b)
        np.testing.assert_array_equal(base_a, base_b)


if __name__ == '__main__':
    unittest.main()
