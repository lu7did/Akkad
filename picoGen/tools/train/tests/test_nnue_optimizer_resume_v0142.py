"""End-to-end smoke with deterministic synthetic data, no chess dependency.
Compares interrupted checkpoint resume against uninterrupted run byte-for-byte.
The synthetic loss tests state handling, NOT chess learning quality.
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ResumeTests(unittest.TestCase):
    def test_resume_matches_uninterrupted(self):
        previous = {k:sys.modules.get(k) for k in ('gen_csv_dataset','gen_fp32_core','genNNUE')}
        try:
            dataset = types.ModuleType('gen_csv_dataset')
            core = types.ModuleType('gen_fp32_core')
            def load_pair(*_args):
                rows = [(None,None,None,float(i-2),None,None) for i in range(6)]
                return rows, rows[:3], 'synthetic-dataset-42', {}
            def padded_features(boards):
                return np.zeros((len(boards),1), dtype=np.int32), np.ones((len(boards),1), dtype=np.int32)
            def nnue_forward(g,x,mask):
                return np.full(len(x), np.float64(g[-1]+g[-2]*0.1),dtype=np.float64)
            def write_json_atomic(p,data):
                Path(p).write_text(json.dumps(data),encoding='utf-8')
            def write_npy_atomic(p,weights):
                np.save(p,weights)
            dataset.load_pair = load_pair
            core.padded_features = padded_features
            core.nnue_forward = nnue_forward
            core.write_json_atomic = write_json_atomic
            core.write_npy_atomic = write_npy_atomic
            sys.modules['gen_csv_dataset'] = dataset
            sys.modules['gen_fp32_core'] = core
            spec = importlib.util.spec_from_file_location('genNNUE', ROOT/'genNNUE.py')
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            def call(output, generations, resume=None):
                args=['genNNUE.py','--train','dummy.csv','--validation','dummy-valid.csv',
                      '--out',str(output),'--population','8','--generations',str(generations),
                      '--seed','42','--mutation-sigma','5']
                if resume: args.extend(['--resume',str(resume)])
                old=sys.argv
                try:
                    sys.argv=args
                    with contextlib.redirect_stdout(io.StringIO()): mod.main()
                finally: sys.argv=old
            with tempfile.TemporaryDirectory() as d:
                d=Path(d)
                x=d/'complete'/'best.npy'; y=d/'resumed'/'best.npy'
                x.parent.mkdir(); y.parent.mkdir()
                call(x,6)
                call(y,3)
                ck=y.parent/'best.evo-v3.gen00003.json'
                self.assertEqual(json.loads(ck.read_text())['generation'],3)
                call(y,6,ck)
                np.testing.assert_array_equal(np.load(x),np.load(y))
                for n in (4,5,6):
                    a=json.loads((x.parent/f'best.evo-v3.gen{n:05d}.json').read_text())
                    b=json.loads((y.parent/f'best.evo-v3.gen{n:05d}.json').read_text())
                    self.assertEqual(a,b)
        finally:
            for k,v in previous.items():
                if v is None:sys.modules.pop(k,None)
                else:sys.modules[k]=v

if __name__ == '__main__': unittest.main()
