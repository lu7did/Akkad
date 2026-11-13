"""Identical INT8 coefficients in C++/PT and quantized MCTSE inference."""
import importlib.util
import math
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class QuantTests(unittest.TestCase):
    def test_export_identical_and_evaluator(self):
        import torch
        from model import build_model
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d);src=d/'best.pt';h=d/'weights.hpp';q=d/'best_int8.pt'
            torch.manual_seed(12)
            net=build_model()
            torch.save({'config':{'features':780,'hidden':16,'policy':'from_to','value':'tanh'},'state_dict':net.state_dict()},src)
            cp=subprocess.run([sys.executable,str(ROOT/'export.py'),'--in',str(src),'--out',str(h),'--int8',str(q)],capture_output=True,text=True)
            self.assertEqual(cp.returncode,0,cp.stderr)
            ck=torch.load(q,weights_only=True)
            self.assertEqual(ck['format'],'picoalpha-nnue-int8-v1')
            text=h.read_text()
            for name,x in ck['weights'].items():
                data=re.search(rf'\b{name}\[\d+\] = \{{(.*?)\}};',text,re.S)
                self.assertIsNotNone(data,name)
                vals=[int(v) for v in re.findall(r'-?\d+',data.group(1))]
                self.assertEqual(vals,x.flatten().tolist())
                scale=re.search(rf'\b{name}_SCALE = ([0-9.eE+-]+)f;',text)
                self.assertIsNotNone(scale)
                self.assertAlmostEqual(float(scale.group(1)),ck['scales'][name],places=14)
            nurse_root=ROOT.parents[2]/'nurse'/'src'
            sys.path.insert(0,str(nurse_root))
            from nurse import mcts_nnue
            evaluator=mcts_nnue.TinyEvaluator(str(q))
            old_feature=mcts_nnue.feature_indices
            old_square=mcts_nnue.square_index
            mcts_nnue.feature_indices=lambda board: [0,11,768,770]
            mcts_nnue.square_index=lambda sq,turn:sq
            class Move:
                def __init__(self,a,b):self.from_square=a;self.to_square=b
            class Board:turn=True
            moves=[Move(1,2),Move(3,4)]
            try:
                value,priors=evaluator.evaluate(Board(),moves)
            finally:
                mcts_nnue.feature_indices=old_feature
                mcts_nnue.square_index=old_square
            self.assertAlmostEqual(sum(priors.values()),1,places=6)
            self.assertTrue(-1 <= value <= 1)
            # Independent integer reference from serialized INT8, not FP32 model.
            w=ck['weights'];sc=ck['scales']
            hidden=w['W_INPUT'].to(torch.int32)[[0,11,768,770]].sum(0).clamp(min=0).to(torch.int32)
            vraw=int((w['W_VALUE'].to(torch.int32)@hidden)[0])
            self.assertAlmostEqual(value,math.tanh(vraw*sc['W_INPUT']*sc['W_VALUE']),places=8)
            # C++ header is syntactically valid if compiler available.
            from shutil import which
            compiler=which('g++') or which('clang++')
            if compiler:
                code=d/'verify.cpp';code.write_text('#include "weights.hpp"\nint main(){return picoalpha_nnue::W_INPUT[0];}\n')
                c=subprocess.run([compiler,'-std=c++17','-fsyntax-only',str(code)],capture_output=True,text=True)
                self.assertEqual(c.returncode,0,c.stderr)

    def test_int8_mandatory_and_reject_fp32(self):
        import torch
        from model import build_model
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d)
            fp=d/'best.pt';torch.save({'config':{'features':780,'hidden':16,'policy':'from_to','value':'tanh'},'state_dict':build_model().state_dict()},fp)
            cmd=[sys.executable,str(ROOT/'export.py'),'--in',str(fp),'--out',str(d/'x.hpp')]
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            sys.path.insert(0,str(ROOT.parents[2]/'nurse'/'src'))
            from nurse.mcts_nnue import TinyEvaluator
            with self.assertRaises(ValueError):TinyEvaluator(str(fp))

if __name__=='__main__':unittest.main()
