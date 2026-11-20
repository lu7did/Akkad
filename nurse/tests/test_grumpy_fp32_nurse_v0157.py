"""Grumpy FP32 Nurse inference regression against picoGen torch arithmetic."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'/'nurse'))
import grumpy_fp32 as g


class NurseGrumpyFP32(unittest.TestCase):
    def test_manifest_contract(self):
        manifest = {'format':g.FORMAT,'dtype':'float32','file':'best.npy',
                    'genes':1680,'architecture':g.ARCHITECTURE,
                    'hidden_clip':32,'fixed_material':list(g.MATERIAL),'output_scale':1}
        g.validate_manifest(manifest)
        for key,val in [('genes',12321),('architecture','other'),('output_scale',400),('fixed_material',[0]*6)]:
            wrong=dict(manifest);wrong[key]=val
            with self.assertRaises(ValueError):g.validate_manifest(wrong)

    def test_forward_matches_torch_training(self):
        import torch
        script = ROOT.parent / 'picoGen' / 'tools' / 'train'
        if not (script / 'gen_grumpy_pgpe_core.py').is_file():
            self.skipTest('picoGen training core not on test filesystem')
        sys.path.insert(0, str(script))
        from gen_grumpy_pgpe_core import forward, to_torch
        rng=np.random.default_rng(5)
        w=rng.normal(0, 0.25, g.GENES).astype(np.float32)
        for count in (2,8,16,32):
            x=np.zeros((2,64),np.int16)
            x[:,:2*count]=rng.integers(0,192,(2,2*count))
            b=(count-2)//4
            feat=(x,2*count,b,500.0,-1)
            data=(x[None],np.array([2*count]),np.array([b]),
                  np.array([500],np.float32),np.array([-1],np.float32),np.array([0],np.float32))
            expected=float(forward(torch.tensor(w),to_torch(data))[0])
            self.assertAlmostEqual(g.forward_features(w,feat),expected,delta=0.001)

    def test_bad_weights_rejected(self):
        feat=(np.zeros((2,64),np.int64),4,0,0.0,1)
        with self.assertRaisesRegex(ValueError,'1680'):
            g.forward_features(np.zeros(12321,np.float32),feat)
        w=np.zeros(1680,np.float32);w[7]=np.nan
        with self.assertRaisesRegex(ValueError,'finite'):
            g.forward_features(w,feat)

if __name__=='__main__':unittest.main()
