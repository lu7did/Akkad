"""Regression tests for PGPE v0.1.49 output parametrization and Nurse export."""
import unittest
import sys
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gen_pgpe_core import (PARAMS, INPUTS, HIDDEN, OUTPUT_GENE_START,
                           OUTPUT_CP_SCALE, export_cp_weights, output_bounds_cp,
                           population_fitness, forward_single_numpy, sigmoid_cp, metrics)

class ScaledOutput(unittest.TestCase):
    def test_scale_only_last_layer_and_keep_signs(self):
        g=np.zeros(PARAMS,dtype=np.float32)
        g[OUTPUT_GENE_START]= -5.0
        g[OUTPUT_GENE_START+1]= 4.0
        g[-1] = -.25
        exported=export_cp_weights(g)
        self.assertTrue(np.array_equal(g[:OUTPUT_GENE_START], exported[:OUTPUT_GENE_START]))
        self.assertEqual(float(exported[OUTPUT_GENE_START]),-2000.)
        self.assertEqual(float(exported[OUTPUT_GENE_START+1]),1600.)
        self.assertEqual(float(exported[-1]),-100.)
        self.assertEqual(output_bounds_cp(exported),(-2100.,1500.))
        self.assertEqual(float(g[OUTPUT_GENE_START]),-5.)  # no optimizer mutation

    def test_fitness_matches_nurse_export(self):
        rng=np.random.default_rng(917)
        g=rng.normal(0,.2,(5,PARAMS)).astype(np.float32)
        x=rng.integers(0,INPUTS,(37,32),dtype=np.int64)
        n=rng.integers(1,33,37,dtype=np.int64)
        y=rng.uniform(-2000,2000,37).astype(np.float32)
        actual=population_fitness(torch.tensor(g),torch.tensor(x),torch.tensor(n),torch.tensor(y),
                  examples_chunk=11,individuals_chunk=2).numpy()
        for k in range(len(g)):
            exported=export_cp_weights(g[k])
            prediction=forward_single_numpy(exported,x,n)
            p=1./(1.+np.exp(-prediction/OUTPUT_CP_SCALE))
            target=1./(1.+np.exp(-y/OUTPUT_CP_SCALE))
            self.assertAlmostEqual(float(actual[k]),float(np.mean((p-target)**2)),places=6)
            self.assertAlmostEqual(metrics(exported,(x,n,y))['mse_probability'],float(actual[k]),places=6)

    def test_symmetric_range_possible_from_zero_hidden_bias(self):
        g=np.zeros(PARAMS,dtype=np.float32)
        g[OUTPUT_GENE_START:OUTPUT_GENE_START+HIDDEN]=np.array([-2.,2.]*8,dtype=np.float32)
        e=export_cp_weights(g)
        lower,upper=output_bounds_cp(e)
        self.assertLessEqual(lower,-2000.)
        self.assertGreaterEqual(upper,2000.)

    def test_checkpoint_identity_cannot_be_legacy(self):
        source=(ROOT/'genPGPE.py').read_text(encoding='utf-8')
        self.assertIn('picogen-pgpe-768x16-prob-scaled-output-v2',source)
        self.assertIn('pgpe-v2.latest.pt',source)

if __name__=='__main__': unittest.main()
