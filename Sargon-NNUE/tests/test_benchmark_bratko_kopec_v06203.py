"""Pruebas del modelo uniforme sin motores externos."""
import unittest
from types import SimpleNamespace
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from sargon_nnue.benchmark_bratko_kopec import compute_matrices, poisson_binomial_tail

class UniformNullTests(unittest.TestCase):
    def test_two_engines_uniform(self):
        suite=[SimpleNamespace(fen=lambda f=f: f) for f in ('fen1','fen2','fen3')]
        rows=[]
        for name,moves in [('A',['a','b','c']),('B',['a','x','c'])]:
            rows.extend(dict(brain=name,mode='positions',round=1,index=i,status='OK',move_uci=m) for i,m in enumerate(moves,1))
        cs, ps, detail=compute_matrices(['A','B'],rows,suite,legal_counts={'fen1':5,'fen2':10,'fen3':20})
        self.assertEqual(cs[0]['B'],'2')
        expect=poisson_binomial_tail([1/5,1/10,1/20],2)
        self.assertAlmostEqual(float(ps[0]['B']),expect,places=6)
        self.assertEqual(ps[1]['A'],ps[0]['B'])
        self.assertEqual(detail[0]['method'],'uniform_legal_moves')
        self.assertEqual(detail[0]['legal_moves_by_position'],[5,10,20])
    def test_no_legal_moves_nd(self):
        suite=[SimpleNamespace(fen=lambda:'fen1')]
        rows=[dict(brain=n,mode='positions',round=1,index=1,status='OK',move_uci='a') for n in ['A','B']]
        _,prob,_=compute_matrices(['A','B'],rows,suite,legal_counts={})
        self.assertEqual(prob[0]['B'],'N/D')
    def test_reference_opt_in(self):
        suite=[SimpleNamespace(fen=lambda:'fen1')]
        rows=[dict(brain=n,mode='positions',round=1,index=1,status='OK',move_uci='a') for n in ['A','B']]
        _,prob,_=compute_matrices(['A','B'],rows,suite,legal_counts={'fen1':5},chance_model='reference')
        self.assertEqual(prob[0]['B'],'N/D')

if __name__ == '__main__': unittest.main()
