"""Regression: genAudit must accept the format emitted by Sargon III genPST."""
import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

TRAIN_DIR = pathlib.Path(__file__).resolve().parents[1]

class TestPstAuditCompatibility(unittest.TestCase):
    def setUp(self):
        # Avoid chess dependency for this format-level regression test.
        self.defaults = {"PAWN_VALUE":100, "KNIGHT_VALUE":310, "BISHOP_VALUE":314}
        stubs = {
            'gen_common': {'atomic_path':lambda *a:None,'require_chess':lambda:None},
            'gen_nnue_core': {'PARAMS':12321,'padded_features':lambda *a:None,'forward':lambda *a:None},
            'gen_pst_core': {'NAMES':('x','y'),'choose_move':lambda *a:None,'evaluate':lambda *a:None},
            'gen_sargon_core': {'DEFAULTS':self.defaults,'evaluate':lambda *a:None},
        }
        self.modules={name:types.ModuleType(name) for name in stubs}
        for name, attrs in stubs.items():
            for key,value in attrs.items():setattr(self.modules[name],key,value)
        with patch.dict(sys.modules,self.modules):
            spec=importlib.util.spec_from_file_location('genAudit_test',TRAIN_DIR/'genAudit.py')
            self.audit=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.audit)
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def load(self,obj):
        path=pathlib.Path(self.temp.name)/'pst.json'
        path.write_text(json.dumps(obj),encoding='utf-8')
        return self.audit.load_pst_parameters(path)

    def test_sargon_model_output(self):
        data,flag=self.load({'format':'picogenus-sargon3-pst-v2','parameters':self.defaults})
        self.assertTrue(flag)
        self.assertEqual(data,self.defaults)

    def test_sargon_pst_best_plain(self):
        data,flag=self.load(self.defaults)
        self.assertTrue(flag)
        self.assertEqual(data,self.defaults)

    def test_sargon_generation_checkpoint(self):
        snap={'format':'picogenus-sargon3-pst-v2','individuals':[{'parameters':self.defaults}],
              'global_best':{'parameters':self.defaults}}
        data,flag=self.load(snap)
        self.assertTrue(flag)
        self.assertEqual(data,self.defaults)

    def test_legacy_david(self):
        data,flag=self.load({'format':'picogenus-pst-v1','parameters':{'x':1,'y':2}})
        self.assertFalse(flag)
        np.testing.assert_array_equal(data,np.array([1,2]))

    def test_schema_error_lists_missing(self):
        with self.assertRaisesRegex(ValueError,'faltan='):
            self.load({'format':'picogenus-sargon3-pst-v2','parameters':{'PAWN_VALUE':100}})

if __name__=='__main__':unittest.main()
