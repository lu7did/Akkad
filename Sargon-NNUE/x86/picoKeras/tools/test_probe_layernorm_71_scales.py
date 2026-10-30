"""Regression tests for all strategies; run with Python NumPy, no TensorFlow required."""
import unittest
import numpy as np
from probe_layernorm_71_scales import affine_params,trial
class ScaleTest(unittest.TestCase):
 def test_static_scalar(self):
  s,z=affine_params(np.arange(32).reshape(2,4,4,1).astype(float))
  self.assertEqual(np.asarray(s).size,1)
  self.assertEqual(np.asarray(z).size,1)
  self.assertEqual(float(np.asarray(s).item()),31/255)
 def test_all_strategies(self):
  rng=np.random.default_rng(7)
  cal=rng.normal(size=(8,2,2,12)).astype(np.float64)
  val=rng.normal(size=(8,2,2,12)).astype(np.float64)
  g=np.ones(12,dtype=np.float64)
  b=np.zeros(12,dtype=np.float64)
  for kind in ('static_tensor','static_channel','dynamic_row'):
   with self.subTest(kind=kind):
    res=trial(val,cal,g,b,1e-5,kind,0.1)
    self.assertTrue(np.isfinite(res['ingress']['max']))
    if kind=='static_channel':self.assertNotIn('end_to_end',res)
    else:self.assertTrue(np.isfinite(res['end_to_end']['max']))
 def test_constant_row(self):
  cal=np.ones((8,2,2,12),dtype=np.float64)
  val=np.ones((8,2,2,12),dtype=np.float64)
  for kind in ('static_tensor','static_channel','dynamic_row'):
   with self.subTest(kind=kind):
    res=trial(val,cal,np.ones(12),np.zeros(12),1e-5,kind,0.1)
    self.assertTrue(np.isfinite(res['ingress']['max']))
if __name__=='__main__':unittest.main()
