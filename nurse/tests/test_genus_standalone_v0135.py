"""Self-contained Nurse GENUS runtime smoke/regression tests.

python-chess is mocked only if not installed in the test environment; the
production runtime uses python-chess normally.
"""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

try:
    import chess
except ImportError:
    stub=types.ModuleType('chess')
    for name, val in {'D4':27,'E4':28,'D5':35,'E5':36,'PAWN':1,'KNIGHT':2,'BISHOP':3,'ROOK':4,'QUEEN':5,'D1':3,'D8':59,'G1':6,'C1':2,'G8':62,'C8':58}.items():
        setattr(stub,name,val)
    sys.modules['chess']=stub

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nurse.genus_eval import GenusEvaluator, resolve_active
from nurse._genus_core import nnue, pst


class Pawn:
    color = True
    piece_type = 1


class MockBoard:
    def piece_map(self):
        return {8:Pawn()}


class TestStandalone(unittest.TestCase):
    def test_pst_v3_uses_bundled_kernel(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'weights.json'
            path.write_text(json.dumps({'format':'picogenus-sargon3-pst-v3','parameters':pst.DEFAULTS}))
            ev=GenusEvaluator('pst',coefficient=str(path))
            with patch.object(pst,'evaluate',return_value=123.55) as func:
                self.assertEqual(ev.evaluate(object()),124)
                func.assert_called_once()
            self.assertEqual(ev.source,str(path.resolve()))

    def test_nnue_int16_exact_formula(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'weights.npy'
            genes=np.zeros(nnue.PARAMS,dtype=np.int16)
            # white pawn on a2 => feature index=8, set 3 input weight + 2 bias
            genes[8*16+0]=3
            genes[768*16+0]=2
            genes[768*16+16+0]=10
            genes[-1]=7
            np.save(p,genes)
            ev=GenusEvaluator('nnue',network=str(p))
            self.assertEqual(ev.evaluate(MockBoard()),57)
            self.assertFalse(ev.network_weights.flags.writeable)

    def test_active_manifest_without_trainer_import(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/'weights.npy'
            actual=Path(d)/'weights.best.g00042.abc.npy'
            np.save(actual,np.ones(nnue.PARAMS,dtype=np.int16))
            (Path(d)/'weights.active.json').write_text(json.dumps({'format':'picogenus-nnue-active-v1','file':actual.name}))
            self.assertEqual(resolve_active(base),actual)
            self.assertEqual(GenusEvaluator('nnue',network=str(base)).source,str(actual))
            (Path(d)/'weights.active.json').write_text(json.dumps({'format':'picogenus-nnue-active-v1','file':'../bad.npy'}))
            with self.assertRaises(ValueError):resolve_active(base)
            (Path(d)/'weights.active.json').write_text(json.dumps({'format':'picogenus-nnue-active-v1','file':'..\\bad.npy'}))
            with self.assertRaises(ValueError):resolve_active(base)

    def test_nnue_legacy_int8_uses_256_scale(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'legacy.npy'
            genes=np.zeros(nnue.PARAMS,dtype=np.int8)
            genes[-1]=64
            np.save(p,genes)
            ev=GenusEvaluator('nnue',network=str(p))
            self.assertEqual(ev.evaluate(MockBoard()),0)
            self.assertAlmostEqual(nnue.forward(genes,*nnue.padded_features([MockBoard()]))[0],0.25)

    def test_no_external_project_imports(self):
        source=Path(__file__).resolve().parents[1]/'src'/'nurse'/'genus_eval.py'
        code=source.read_text()
        self.assertNotIn("/ 'picoGenus'",code)
        self.assertNotIn('importlib',code)
        self.assertNotIn('gen_nnue_storage',code)
        self.assertNotIn('gen_nnue_core\'\')',code)

if __name__=='__main__':unittest.main()
