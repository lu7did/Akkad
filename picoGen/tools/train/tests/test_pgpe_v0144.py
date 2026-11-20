"""CPU contract tests; no EvoTorch or chess dependency required for these tests."""
import sys
import unittest
import tempfile
import json
import types
from unittest.mock import patch
from pathlib import Path
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
NURSE=ROOT.parents[2]/'nurse'/'src'
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(NURSE))
from gen_pgpe_core import PARAMS,population_fitness,forward_single_numpy,metrics
from nurse._genus_core import nnue


class PGPEContracts(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(PARAMS,12321)
        self.assertEqual(nnue.PARAMS,PARAMS)

    def test_population_fitness_matches_numpy(self):
        rng=np.random.default_rng(17)
        genes=rng.normal(0,.5,(4,PARAMS)).astype(np.float32)
        x=rng.integers(0,768,(27,32),dtype=np.int64)
        n=rng.integers(1,33,27,dtype=np.int64)
        y=rng.normal(0,500,27).astype(np.float32)
        actual=population_fitness(torch.tensor(genes),torch.tensor(x),torch.tensor(n),torch.tensor(y),
                                  examples_chunk=7,individuals_chunk=2).numpy()
        for i in range(4):
            np_pred=forward_single_numpy(genes[i],x,n)
            ideal=1/(1+np.exp(-np_pred/400))
            labels=1/(1+np.exp(-y/400))
            expected=np.mean((ideal-labels)**2)
            self.assertAlmostEqual(float(actual[i]),float(expected),places=6)

    def test_nurse_same_activation_and_white_perspective(self):
        rng=np.random.default_rng(91)
        weights=rng.normal(0,.3,PARAMS).astype(np.float32)
        idx=rng.integers(0,768,(4,32),dtype=np.int64)
        lengths=np.array([2,11,24,32],dtype=np.int64)
        mask=np.arange(32)[None,:]<lengths[:,None]
        np_scores=forward_single_numpy(weights,idx,lengths)
        nurse_scores=nnue.forward(weights,idx.astype(np.int32),mask.astype(np.int64),clip_max=1)
        np.testing.assert_allclose(np_scores,nurse_scores,atol=1e-4,rtol=1e-5)
        old=nnue.forward(weights,idx.astype(np.int32),mask.astype(np.int64))
        self.assertFalse(np.allclose(old,np_scores))

    def test_nurse_manifest_selects_clip_without_breaking_legacy(self):
        with patch.dict(sys.modules, {'nurse._genus_core.pst':types.ModuleType('nurse._genus_core.pst')}):
            from nurse.genus_eval import GenusEvaluator
        class Piece:
            def __init__(self,piece_type,color):
                self.piece_type,self.color=piece_type,color
        class Board:
            def piece_map(self):
                return {4:Piece(6,True),60:Piece(6,False),12:Piece(1,True)}
        rng=np.random.default_rng(123)
        weights=np.zeros(PARAMS,dtype=np.float32)
        weights[768*16:768*16+16] = 2.0
        weights[768*16+16:-1] = 5.0
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'best.npy'
            np.save(file,weights)
            metadata={'format':'picogen-nnue-pgpe-active-fp32-v1','dtype':'float32',
                      'file':'best.npy','genes':PARAMS,'output_scale':1,
                      'input_features':768,'hidden':16,'hidden_clip':1,
                      'feature_schema':'piece-square-768-white-perspective-v1'}
            (Path(d)/'best.active.json').write_text(json.dumps(metadata))
            pgpe=GenusEvaluator('nnue',network=file)
            self.assertEqual(pgpe.nnue_clip_max,1)
            a=pgpe.evaluate(Board())
            metadata['format']='picogen-nnue-active-fp32-v1'
            (Path(d)/'best.active.json').write_text(json.dumps(metadata))
            legacy=GenusEvaluator('nnue',network=file)
            self.assertEqual(legacy.nnue_clip_max,127)
            b=legacy.evaluate(Board())
            self.assertNotEqual(a,b)

    def test_zero_predictions_probability(self):
        genes=np.zeros((2,PARAMS),dtype=np.float32)
        x=np.zeros((3,32),dtype=np.int64)
        n=np.ones(3,dtype=np.int64)
        y=np.zeros(3,dtype=np.float32)
        s=population_fitness(torch.tensor(genes),torch.tensor(x),torch.tensor(n),torch.tensor(y))
        np.testing.assert_allclose(s.numpy(),[0,0],atol=1e-9)
        self.assertEqual(metrics(genes[0],(x,n,y))['rmse_cp'],0.0)

if __name__=='__main__':unittest.main()
