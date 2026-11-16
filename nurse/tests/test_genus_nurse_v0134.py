"""Self-contained regression checks for Nurse picoGenus integration.

Integration chess tests require user-installed python-chess and actual model files.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from nurse.config import read_brain
from nurse.genus_eval import GenusEvaluator


class FakePSTCore:
    DEFAULTS={'PAWN_VALUE':100,'KNIGHT_VALUE':310}
    SPECS=[('KNIGHT_VALUE',11,0,2047)]
    @staticmethod
    def evaluate(board,params):return params['KNIGHT_VALUE']-100


class FakeNNUECore:
    PARAMS=5
    @staticmethod
    def padded_features(boards):return np.zeros((len(boards),1),dtype=int),np.ones((len(boards),1),dtype=int)
    @staticmethod
    def forward(weights,x,mask):return np.asarray([float(weights.sum())]*len(x))


class FakeStorage:
    @staticmethod
    def resolve_active(path):return path


def module(name):
    return {'gen_sargon_core':FakePSTCore,'gen_nnue_core':FakeNNUECore,'gen_nnue_storage':FakeStorage}[name]


class GenusNurseTests(unittest.TestCase):
    def test_pst_v3_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'genus_pst.json'
            path.write_text(json.dumps({'format':'picogenus-sargon3-pst-v3','parameters':{'PAWN_VALUE':100,'KNIGHT_VALUE':310}}))
            with patch('nurse.genus_eval._module',side_effect=module):
                ev=GenusEvaluator('pst',coefficient=str(path))
                self.assertEqual(ev.evaluate(None),210)
    def test_pst_best_bare_coefficients(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'PST_best.json'
            path.write_text(json.dumps({'PAWN_VALUE':100,'KNIGHT_VALUE':310}))
            with patch('nurse.genus_eval._module',side_effect=module):
                self.assertEqual(GenusEvaluator('pst',coefficient=str(path)).evaluate(None),210)
    def test_nnue_int16_unscaled(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'genus_nnue.npy'
            np.save(path,np.asarray([1,2,3,4,5],dtype=np.int16))
            with patch('nurse.genus_eval._module',side_effect=module):
                ev=GenusEvaluator('nnue',network=str(path))
                self.assertEqual(ev.evaluate(None),15)
                self.assertFalse(ev.network_weights.flags.writeable)
    def test_invalid_model_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pst.json';path.write_text(json.dumps({'format':'unrecognized','parameters':{}}))
            with patch('nurse.genus_eval._module',side_effect=module):
                with self.assertRaises(ValueError):GenusEvaluator('pst',coefficient=str(path))
    def test_config_uses_same_sargon_search(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'pst.json').write_text('{}')
            (p/'nnue.npy').write_bytes(b'placeholder')
            entries={k:{'type':'nurse','player':'sargon','evaluator':{'evaluator':ev,'network':str(p/file)},'Depth':3,'QDepth':2,'tmax':15000,'timeout':30000}
                     for k,ev,file in [('pst','genus-pst','pst.json'),('nnue','genus-nnue','nnue.npy')]}
            cfg=p/'brains.json';cfg.write_text(json.dumps({'brains':entries}))
            a=read_brain(cfg,'pst');b=read_brain(cfg,'nnue')
            self.assertEqual(a['_player'],b['_player'])
            self.assertEqual(a['_player'],'sargon')
            self.assertEqual(a['_network'],str(p/'pst.json'))
            self.assertEqual(b['_network'],str(p/'nnue.npy'))

if __name__=='__main__':unittest.main()
