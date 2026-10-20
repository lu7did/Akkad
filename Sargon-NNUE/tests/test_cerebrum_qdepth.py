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
#* test_cerebrum_qdepth.py
#* Ejecuta pruebas de regresion para test cerebrum qdepth
#* v0.6.153
#=================================================================================================================*
import unittest
import chess
from sargon_nnue.players.cerebrum_player import CerebrumPlayer

class MaterialEvaluator:
    def evaluate(self, board):
        vals={chess.PAWN:100,chess.KNIGHT:300,chess.BISHOP:300,chess.ROOK:500,chess.QUEEN:900}
        return sum(vals.get(p.piece_type,0)*(1 if p.color else -1) for p in board.piece_map().values())

class QuiescenceTests(unittest.TestCase):
    def test_default_remains_zero(self):
        self.assertEqual(CerebrumPlayer(MaterialEvaluator()).qdepth,0)
    def test_moves_are_legal_and_board_unchanged(self):
        for q in (0,1,2,3):
            b=chess.Board()
            fen=b.fen()
            choice=CerebrumPlayer(MaterialEvaluator(),qdepth=q).choose(b)
            self.assertIn(choice.move,b.legal_moves)
            self.assertEqual(b.fen(),fen)
    def test_qsearch_mate(self):
        p=CerebrumPlayer(MaterialEvaluator(),qdepth=2)
        board=chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1')
        self.assertLess(p._terminal_white_score(board),0) if False else self.assertGreater(p._terminal_white_score(board),0)

if __name__=='__main__':unittest.main()
