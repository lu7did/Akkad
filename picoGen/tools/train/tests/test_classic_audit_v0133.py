"""Verify numeric audit: 3 evaluators, paired metrics, canonical CLASSIC parity."""
import ast
import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
import zipfile
from unittest.mock import patch

import numpy as np

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=pathlib.Path('/mnt/data/akkad(20261113-010040).zip')

class TestClassicPort(unittest.TestCase):
    def test_exact_algorithmic_ast_against_baseline(self):
        if not BASE.exists(): self.skipTest('baseline archive not installed in deployment')
        with zipfile.ZipFile(BASE) as z:
            original=z.read('Sargon-NNUE/src/sargon_nnue/evaluators/classic.py').decode('utf-8-sig')
        port=(ROOT/'gen_classic_core.py').read_text()
        def key_functions(source):
            tree=ast.parse(source)
            clas=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='ClassicEvaluator')
            return [(x.name,ast.dump(x,include_attributes=False)) for x in clas.body if isinstance(x,ast.FunctionDef)]
        self.assertEqual(key_functions(original),key_functions(port))

class FakeBoard:
    def __init__(self,name):self.name=name
    def fen(self,**kw):return self.name

class TestNumericAudit(unittest.TestCase):
    def setUp(self):
        self.mods={}
        specifications={
            'gen_common':{'atomic_path':lambda *a:None,'require_chess':lambda:None},
            'gen_nnue_core':{'PARAMS':12321,'padded_features':lambda boards:(boards,), 'forward':lambda nnue,boards:np.array([nnue[b.name] for b in boards])},
            'gen_pst_core':{'NAMES':('x','y'),'evaluate':lambda board,pst:pst[board.name]},
            'gen_sargon_core':{'DEFAULTS':{'a':1},'evaluate':lambda board,pst:pst[board.name]},
            'genBP':{'epd_after_best_move':lambda *a:None},
            'gen_classic_core':{'evaluate_classic':lambda b:{'one':10,'two':-20,'three':0}[b.name]},
        }
        for name,values in specifications.items():
            mod=types.ModuleType(name)
            for attr,v in values.items():setattr(mod,attr,v)
            self.mods[name]=mod
        with patch.dict(sys.modules,self.mods):
            spec=importlib.util.spec_from_file_location('genAudit_v133_test',ROOT/'genAudit.py')
            self.mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.mod)

    def test_three_methods_pairwise_comparison(self):
        suite=[(FakeBoard('one'),12.0,'A'),(FakeBoard('two'),-25.0,'B'),(FakeBoard('three'),8.0,'C')]
        pst={'one':11,'two':-22,'three':7}
        nnue={'one':9,'two':-26,'three':1}
        result=self.mod.audit(suite,pst,nnue)
        self.assertEqual(set(result['methods']),{'CLASSIC','PST','NNUE'})
        self.assertEqual(result['format'],'picogenus-post-bm-numeric-audit-v3')
        self.assertEqual(len(result['cases']),9)
        self.assertEqual(result['versus_classic']['PST']['positions_better_than_classic'],3)
        self.assertGreater(result['versus_classic']['PST']['stockfish_rmse_improvement_cp'],0)
        self.assertAlmostEqual(result['versus_classic']['PST']['rmse_to_classic_cp'],np.sqrt((1+4+49)/3))
        for item in result['cases']:
            if item['predictor']!='CLASSIC':
                self.assertIn('difference_to_classic_cp',item)
                self.assertIn('beats_classic_vs_stockfish',item)
        self.assertEqual(result['classic_reference']['perspective'],'white')

    def test_v3_pst_model_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            f=pathlib.Path(folder)/'pst.json'
            f.write_text(json.dumps({'format':'picogenus-sargon3-pst-v3','parameters':{'a':1}}))
            params,flag=self.mod.load_pst_parameters(f)
            self.assertTrue(flag)
            self.assertEqual(params,{'a':1})

if __name__=='__main__': unittest.main()
