"""Host verification; execute: python -m unittest discover -s nurse/train/tests."""
import sys, unittest, tempfile, pathlib, subprocess
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from common import SHAPES,validate_npz,save_npz_atomic
from export import quantize,emit_hpp
class TestContract(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            rng=np.random.default_rng(42)
            arr={k:rng.normal(size=s) for k,s in SHAPES.items()}
            path=pathlib.Path(d)/'model.npz';save_npz_atomic(path,arr)
            recovered=validate_npz(path)
            for key in arr:np.testing.assert_array_equal(arr[key],recovered[key])
    def test_flash_header_compile(self):
        zero={k:np.zeros(shape) for k,shape in SHAPES.items()}
        quant,scales=quantize(zero)
        header=emit_hpp(quant,scales,'nurse_npz_int8')
        self.assertIn('= 1.0f;',header)
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);(p/'weights.hpp').write_text(header)
            (p/'test.cpp').write_text('#include "weights.hpp"\nint main(){return int(nurse_npz_int8::W_IH[0]);}\n')
            # If compiler exists, compile actual C++ syntax.
            import shutil
            compiler=shutil.which('g++') or shutil.which('clang++')
            if compiler:
                x=subprocess.run([compiler,'-std=c++17','-fsyntax-only',str(p/'test.cpp')],capture_output=True,text=True)
                self.assertEqual(x.returncode,0,x.stderr)
if __name__=='__main__':unittest.main()
