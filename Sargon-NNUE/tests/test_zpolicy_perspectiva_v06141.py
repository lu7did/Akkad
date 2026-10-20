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
#* test_zpolicy_perspectiva_v06141.py
#* Regresiones de perspectiva y backup para AlphaZero+znpz/zclassic.
#* v0.6.153
#=================================================================================================================*
"""Regresiones de perspectiva y backup para AlphaZero+znpz/zclassic."""
import math
import unittest

import chess
from sargon_nnue.evaluators.base import Evaluator
from sargon_nnue.evaluators.zpolicy import ValuePolicyEvaluator
from sargon_nnue.players.alphazero import AlphaZeroPlayer, _Node


class WhiteCp(Evaluator):
    name = 'WHITE-CP-TEST'

    def __init__(self, root_cp=0):
        self.root_cp = root_cp

    def evaluate(self, board):
        if board.move_stack:
            last = board.peek().uci()
            if last == 'e2e4':
                return 200
            if last == 'd2d4':
                return 50
            if last == 'e7e5':
                return -200
            if last == 'd7d5':
                return -50
        return self.root_cp


class SignAudit(unittest.TestCase):
    def test_root_value_is_from_side_to_move_not_white(self):
        ev = ValuePolicyEvaluator(WhiteCp(200), name='T', network_id='T')
        white = chess.Board()
        black = chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')
        self.assertAlmostEqual(ev.evaluate_pv(white).q, math.tanh(.25))
        self.assertAlmostEqual(ev.evaluate_pv(black).q, -math.tanh(.25))

    def test_successor_policy_white_prefers_positive_white_cp(self):
        board = chess.Board()
        ev = ValuePolicyEvaluator(WhiteCp(), name='T', network_id='T')
        initial_fen = board.fen()
        p = ev.evaluate_pv(board).policy
        self.assertEqual(max(p, key=p.get).uci(), 'e2e4')
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertEqual(set(p), set(board.legal_moves))
        self.assertEqual(board.fen(), initial_fen)
        self.assertEqual(len(board.move_stack), 0)

    def test_successor_policy_black_prefers_negative_white_cp(self):
        board = chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')
        ev = ValuePolicyEvaluator(WhiteCp(), name='T', network_id='T')
        p = ev.evaluate_pv(board).policy
        self.assertEqual(max(p, key=p.get).uci(), 'e7e5')
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertEqual(set(p), set(board.legal_moves))

    def test_backup_negates_once_white_and_black(self):
        ev = ValuePolicyEvaluator(WhiteCp(), name='T', network_id='T')
        pl = AlphaZeroPlayer(ev, simulations=1, tmax_ms=60000)
        boards = [chess.Board(),
                  chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')]
        for board, expected in zip(boards, ('e2e4', 'e7e5')):
            with self.subTest(turn=board.turn):
                root = _Node(board.turn)
                pl._expand(root, board)
                pl._simulation(root, board.copy(stack=True))
                move = chess.Move.from_uci(expected)
                self.assertEqual(sum(root.visits.values()), 1)
                self.assertEqual(root.visits[move], 1)
                self.assertGreater(root.totals[move], 0.)
                self.assertAlmostEqual(root.totals[move], math.tanh(.25), places=9)

    def test_mate_terminal_for_both_perspectives(self):
        # Esta FEN contiene VARIOS mates en una jugada; no hay uno unico.
        # El criterio correcto es elegir CUALQUIER mate legal, en ambos colores.
        ev = ValuePolicyEvaluator(WhiteCp(), name='T', network_id='T')
        white = chess.Board('7k/5K2/6Q1/8/8/8/8/8 w - - 0 1')
        for board in (white, white.mirror()):
            with self.subTest(turn='white' if board.turn else 'black'):
                fen_before = board.fen()
                stack_before = len(board.move_stack)
                p = ev.evaluate_pv(board).policy
                self.assertEqual(set(p), set(board.legal_moves))
                self.assertAlmostEqual(sum(p.values()), 1.0)
                mate_moves = []
                for move in list(board.legal_moves):
                    board.push(move)
                    try:
                        if board.is_checkmate():
                            mate_moves.append(move)
                            # La hoja es derrota para quien debe mover ahora.
                            self.assertAlmostEqual(ev.evaluate_pv(board).q, -1.0)
                    finally:
                        board.pop()
                self.assertGreaterEqual(len(mate_moves), 2)
                self.assertIn(max(p, key=p.get), mate_moves)
                best_mate_prior = p[mate_moves[0]]
                for move in mate_moves:
                    self.assertAlmostEqual(p[move], best_mate_prior, places=12)
                others = [p[move] for move in p if move not in mate_moves]
                if others:
                    self.assertGreater(best_mate_prior, max(others))
                self.assertEqual(board.fen(), fen_before)
                self.assertEqual(len(board.move_stack), stack_before)


if __name__ == '__main__':
    unittest.main()
