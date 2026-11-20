"""FP32 genetic core tests. Run on Windows after installing requirements."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gen_fp32_core import (PST_NAMES, PARAMS, FORMAT, nnue_forward, nnue_initial,
                           nnue_breed, pst_initial, pst_breed, pst_params,
                           gaussian_mutation)

class FP32Genetics(unittest.TestCase):
    def test_initialization_and_genome_sizes(self):
        rng=np.random.default_rng(42)
        pst=pst_initial(rng,30);nn=nnue_initial(rng,30)
        self.assertEqual(pst.shape,(30,len(PST_NAMES)))
        self.assertEqual(nn.shape,(30,PARAMS))
        self.assertEqual(nn.dtype,np.float32)
        self.assertEqual(pst.dtype,np.float32)
        self.assertEqual(pst_params(pst[0])['PAWN_VALUE'],100.)
    def test_gaussian_rate_and_determinism(self):
        a=np.zeros(300000,dtype=np.float32)
        x,n=gaussian_mutation(a.copy(),np.random.default_rng(42),3.0)
        y,m=gaussian_mutation(a.copy(),np.random.default_rng(42),3.0)
        self.assertEqual(n,m)
        self.assertTrue(np.array_equal(x,y))
        self.assertTrue(8500<n<9500)
        self.assertGreater(float(x.std()),0.)
    def test_breeding_float(self):
        rng=np.random.default_rng(123)
        pst=pst_initial(rng,30)
        nn=nnue_initial(rng,30)
        pst_children,_=pst_breed(pst,np.arange(30,dtype=float),rng,3.)
        nn_children,_=nnue_breed(nn,np.arange(30,dtype=float),rng,3.)
        self.assertEqual(pst_children.dtype,np.float32)
        self.assertEqual(nn_children.dtype,np.float32)
        self.assertTrue(np.array_equal(pst_children[0],pst[0]))
        self.assertTrue(np.array_equal(nn_children[0],nn[0]))
    def test_forward_float32(self):
        g=nnue_initial(np.random.default_rng(42),1)[0]
        x=np.zeros((2,32),dtype=np.int32)
        m=np.zeros((2,32),dtype=np.int64)
        value=nnue_forward(g,x,m)
        self.assertEqual(value.shape,(2,))
        self.assertTrue(np.isfinite(value).all())
        with self.assertRaises(ValueError):nnue_forward(g.astype(np.int16),x,m)
    def test_format_version(self):
        self.assertEqual(FORMAT,'picogen-binpack-genetic-fp32-v1')

if __name__=='__main__':unittest.main()
