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
#* test_lc0_architecture.py
#* Run in Sargon environment: python -m unittest discover -s tests -p 'test_lc0_architecture.py'.
#* v0.6.153
#=================================================================================================================*
"""Run in Sargon environment: python -m unittest discover -s tests -p 'test_lc0_architecture.py'.
No real LC0 network needed; verifies search, WDL, history, and compatibility contracts.
"""
import unittest
import chess
from sargon_nnue.evaluators.lc0 import NeuralEvaluation, wdl_from_qd, cp_from_q
from sargon_nnue.players.alphazero import AlphaZeroPlayer

class MockLC0:
    """LC0 protocol test double; no neural inference."""
    name='LC0'
    def __init__(self):self.calls=0;self.network_id='mock'
    def new_game(self): pass
    def evaluate_pv(self,board):
        self.calls+=1
        moves=list(board.legal_moves)
        p={m:1/len(moves) for m in moves}
        return NeuralEvaluation(p,0.40,0.20,0.40,'COMPLETE','mock')

class ArchitectureTests(unittest.TestCase):
    def test_wdl_normalization(self):
        w,d,l=wdl_from_qd(.4,.3)
        self.assertAlmostEqual(w,.55)
        self.assertAlmostEqual(d,.3)
        self.assertAlmostEqual(l,.15)
        self.assertAlmostEqual(cp_from_q(0),0)
    def test_mcts_legal_and_visits(self):
        from unittest.mock import patch
        # Interface test bypasses LC0 backend availability, checks PUCT itself.
        mock=MockLC0()
        with patch('sargon_nnue.players.alphazero.LC0Evaluator',MockLC0):
            player=AlphaZeroPlayer(mock,simulations=16,cpuct=1.5,tmax_ms=60000)
        board=chess.Board()
        answer=player.choose(board.copy(stack=True))
        self.assertIn(answer.move,board.legal_moves)
        self.assertEqual(sum(player.last_visits.values()),16)
        self.assertGreaterEqual(mock.calls,2)
    def test_move_and_history_not_lost(self):
        b=chess.Board()
        for m in ['e2e4','e7e5','g1f3']:b.push_uci(m)
        self.assertEqual(len(b.copy(stack=True).move_stack),3)
        self.assertEqual(len(b.copy(stack=False).move_stack),0)

if __name__=='__main__':unittest.main()
