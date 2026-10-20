#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_zpolicy_v06138.py
#* version 0.6.138: run `python -m unittest tests.test_zpolicy_v06138` with python-chess/numpy.
#* v0.6.153
#=================================================================================================================*
"""v0.6.138: run `python -m unittest tests.test_zpolicy_v06138` with python-chess/numpy."""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace

import chess
import numpy as np

from sargon_nnue.brains import validate, to_argv
from sargon_nnue.cli_common import add_engine_args
from sargon_nnue.evaluators import create_evaluator
from sargon_nnue.evaluators.zpolicy import _priors, ValuePolicyEvaluator, ZClassicEvaluator
from sargon_nnue.evaluators.base import Evaluator, EvaluatorError
from sargon_nnue.players.alphazero import AlphaZeroPlayer
from sargon_nnue.players.base import PlayerError
from sargon_nnue.sargon_match import add_side, cmd_side
from sargon_nnue.factory import build_engine
from sargon_nnue.evaluators.npz import INPUT_SIZE,HIDDEN_SIZE

class FixedEval(Evaluator):
    name = 'FIXED'
    def __init__(self, cp):self.cp = cp
    def evaluate(self, board): return self.cp


class ValuePolicyTests(unittest.TestCase):
    def test_softmax_and_numeric_safety(self):
        p = _priors([100, 0, -100], 100, 0.01)
        self.assertAlmostEqual(sum(p), 1, places=13)
        self.assertGreater(p[0],p[1]);self.assertGreater(p[1],p[2]);self.assertGreater(p[2],0)
        p = _priors([1e12, -1e12], 100, 0.01)
        self.assertAlmostEqual(sum(p), 1)
        self.assertGreater(min(p),0)
        with self.assertRaises(EvaluatorError):_priors([float('nan')],100,0.01)

    def test_pv_normalized_white_and_black_and_no_mutation(self):
        ev = ValuePolicyEvaluator(FixedEval(150), name='TEST',network_id='test')
        for board in (chess.Board(), chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')):
            saved_fen=board.fen();saved_moves=list(board.move_stack)
            out=ev.evaluate_pv(board)
            self.assertEqual(set(out.policy),set(board.legal_moves))
            self.assertAlmostEqual(sum(out.policy.values()),1,places=12)
            self.assertTrue(all(x>0 for x in out.policy.values()))
            self.assertAlmostEqual(out.w+out.d+out.l,1.0)
            self.assertGreater(out.q,0 if board.turn==chess.WHITE else -1.0)
            self.assertEqual(board.fen(),saved_fen)
            self.assertEqual(board.move_stack,saved_moves)
        self.assertGreater(ev.evaluate_pv(chess.Board()).q,0)
        self.assertLess(ev.evaluate_pv(chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')).q,0)

    def test_mate_is_prioritized_and_terminal_value_exact(self):
        # White has mate in one: Qg7#.
        b=chess.Board('7k/5K2/6Q1/8/8/8/8/8 w - - 0 1')
        ev=ValuePolicyEvaluator(FixedEval(-20),name='TEST',network_id='test')
        info=ev.evaluate_pv(b)
        self.assertIn(chess.Move.from_uci('g6g7'),info.policy)
        self.assertEqual(info.policy[chess.Move.from_uci('g6g7')],max(info.policy.values()))
        b.push_uci('g6g7')
        self.assertTrue(b.is_checkmate())
        terminal=ev.evaluate_pv(b)
        self.assertEqual(terminal.q,-1.0)
        self.assertFalse(terminal.policy)

    def test_parameters_rejected(self):
        for kw in ({'temperature':0},{'temperature':float('nan')},
                   {'value_scale':0},{'uniform_mix':1},{'uniform_mix':-0.1}):
            with self.assertRaises(EvaluatorError):
                ValuePolicyEvaluator(FixedEval(0),name='TEST',network_id='t',**kw)

    def test_alphazero_zclassic_and_old_lc0_gate(self):
        ev=ZClassicEvaluator()
        pl=AlphaZeroPlayer(ev,simulations=5,cpuct=1.5,tmax_ms=60000)
        for b in (chess.Board(),chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')):
            choice=pl.choose(b)
            self.assertIn(choice.move,b.legal_moves)
            self.assertEqual(sum(pl.last_visits.values()),5)
        with self.assertRaises(PlayerError):AlphaZeroPlayer(FixedEval(0))

    def test_factory_and_brains(self):
        cfg={'player':'alphazero','evaluator':'zclassic','az-simulations':3,
             'z-temperature':75.0,'z-value-scale':800.0,'z-uniform-mix':0.02}
        self.assertEqual(validate(cfg),cfg)
        import argparse
        p=argparse.ArgumentParser()
        add_engine_args(p)
        args=p.parse_args(to_argv(cfg))
        ev,pl=build_engine(args)
        self.assertEqual(ev.name,'ZCLASSIC')
        self.assertEqual(pl.simulations,3)
        self.assertEqual(pl.choose(chess.Board()).move in chess.Board().legal_moves,True)
        with self.assertRaises(ValueError):validate({'player':'alphazero','evaluator':'znpz'})
        with self.assertRaises(ValueError):validate({'player':'alphazero','evaluator':'classic'})

    def test_npz_checkpoint_and_player(self):
        with TemporaryDirectory() as tmp:
            f=Path(tmp)/'weights.npz'
            np.savez(f,w_ih=np.zeros((INPUT_SIZE,HIDDEN_SIZE)),b_h=np.zeros(HIDDEN_SIZE),
                     w_ho=np.zeros((HIDDEN_SIZE,1)),b_o=0.0,hm_w=0.0)
            ev=create_evaluator('znpz',str(f))
            out=ev.evaluate_pv(chess.Board())
            self.assertAlmostEqual(sum(out.policy.values()),1)
            self.assertEqual(len(out.policy),20)
            pl=AlphaZeroPlayer(ev,simulations=3)
            self.assertIn(pl.choose(chess.Board()).move,chess.Board().legal_moves)
            ev.close()

    def test_match_side_roundtrip(self):
        import argparse
        p=argparse.ArgumentParser()
        add_side(p,'a')
        a=p.parse_args(['--a-player','alphazero','--a-evaluator','zclassic',
                        '--a-z-temperature','75.0'])
        a.python='python';a.boost_audit_dir=None
        cmd=cmd_side(a,'a')
        self.assertIn('zclassic',cmd)
        self.assertEqual(cmd[cmd.index('--z-temperature')+1],'75.0')

if __name__=='__main__':unittest.main()
