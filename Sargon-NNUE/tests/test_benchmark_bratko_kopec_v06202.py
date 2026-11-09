"""Tests aislados del conjunto BK y del cálculo estadístico, sin motores externos."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sargon_nnue.benchmark_bratko_kopec import (
    BK_FORSYTH, choose_positions, poisson_binomial_tail, compute_matrices,
)

class BKTests(unittest.TestCase):
    def test_complete_suite_and_reproducibility(self):
        self.assertEqual(len(BK_FORSYTH), 24)
        a, b = choose_positions(10, 738), choose_positions(10, 738)
        self.assertEqual(a, b)
        self.assertEqual(len({i for i, _ in a}), 10)
        self.assertTrue(all(fen.endswith('- - 0 1') for _, fen in a))
        for i, (board, turn) in enumerate(BK_FORSYTH):
            self.assertEqual(len(board.split('/')), 8)
            self.assertEqual(board.count('K'), 1)
            self.assertEqual(board.count('k'), 1)
            for rank in board.split('/'):
                self.assertEqual(sum(int(c) if c.isdigit() else 1 for c in rank), 8)
        with self.assertRaises(ValueError): choose_positions(25, 1)

    def test_exact_tail(self):
        self.assertAlmostEqual(poisson_binomial_tail([0.5]*10, 8), 56/1024)
        self.assertAlmostEqual(poisson_binomial_tail([0.1]*2, 1), .19)
        self.assertEqual(poisson_binomial_tail([0.9,0.2], 0), 1)

    def test_two_engines_no_reference_is_nd(self):
        suite = [SimpleNamespace(fen=lambda: 'fen1')]
        rows = [dict(brain=x,mode='positions',round=1,index=1,status='OK',move_uci='a2a3') for x in ('A','B')]
        cs,ps,detail = compute_matrices(['A','B'],rows,suite,legal_counts={'fen1':5},chance_model='reference')
        self.assertEqual(cs[0]['B'], '1')
        self.assertEqual(ps[0]['B'], 'N/D')
        self.assertEqual(ps[1]['A'], 'N/D')

    def test_leave_pair_out_and_symmetric(self):
        suite = [SimpleNamespace(fen=lambda: 'fen1'),SimpleNamespace(fen=lambda: 'fen2')]
        rows = []
        for x,moves in {'A':['a2a3','b2b3'],'B':['a2a3','c2c3'],
                        'C':['a2a3','b2b3'],'D':['a2a4','b2b4']}.items():
            for i,move in enumerate(moves,1):
                rows.append(dict(brain=x,mode='positions',round=1,index=i,status='OK',move_uci=move))
        cs,ps,detail = compute_matrices(['A','B','C','D'],rows,suite,
                                        legal_counts={'fen1':5,'fen2':5},chance_model='reference')
        self.assertEqual(cs[0]['B'],'1')
        self.assertEqual(cs[0]['C'],'2')
        self.assertEqual(cs[0]['D'],'0')
        self.assertEqual(cs[1]['A'],cs[0]['B'])
        self.assertEqual(ps[0]['B'],ps[1]['A'])
        self.assertNotEqual(ps[0]['B'],'N/D')
        self.assertEqual(ps[0]['A'],'—')
        self.assertEqual(len(detail),6)
        self.assertEqual(ps[0]['D'],'1')

    def test_missing_result_is_not_zero(self):
        suite = [SimpleNamespace(fen=lambda: 'fen1')]
        cs,ps,_ = compute_matrices(['A','B'],[dict(brain='A',round=1,index=1,mode='positions',status='OK',move_uci='a2a3')],suite,legal_counts={'fen1':5})
        self.assertEqual(cs[0]['B'],'N/D')
        self.assertEqual(ps[0]['B'],'N/D')

if __name__=='__main__': unittest.main()
