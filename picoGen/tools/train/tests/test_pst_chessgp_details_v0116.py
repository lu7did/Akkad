"""Regresiones v0.1.16; python-chess requerido para ejecución de tablero."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import chess
    from gen_pst_core import _backward_pawn, _clear_file_between, evaluate, PARAM_SPECS
except ImportError:
    chess = None

@unittest.skipIf(chess is None, 'requiere python-chess')
class TestChessGpCompatibleDetails(unittest.TestCase):
    def test_chromosome_unchanged(self):
        self.assertEqual(len(PARAM_SPECS), 34)
        self.assertEqual(sum(width for _,width in PARAM_SPECS),224)

    def test_backward_pawn_front_square_must_be_empty(self):
        # White pawn d3, adjacent own pawn e4, black pawn c5 controls d4.
        fen_clear='4k3/8/8/2p5/4P3/3P4/8/4K3 w - - 0 1'
        b=chess.Board(fen_clear)
        self.assertTrue(_backward_pawn(b,chess.D3,chess.WHITE))
        # Same structure but d4 is occupied: not a backward pawn under ChessGP.
        fen_blocked='4k3/8/8/2p5/3nP3/3P4/8/4K3 w - - 0 1'
        b=chess.Board(fen_blocked)
        self.assertFalse(_backward_pawn(b,chess.D3,chess.WHITE))

    def test_file_path_ignores_endpoints_but_not_intervening(self):
        clear=chess.Board('4k3/8/8/4P3/8/8/4R3/4K3 w - - 0 1')
        blocked=chess.Board('4k3/8/8/4P3/8/4B3/4R3/4K3 w - - 0 1')
        self.assertTrue(_clear_file_between(clear,chess.E2,chess.E5))
        self.assertFalse(_clear_file_between(blocked,chess.E2,chess.E5))

    def test_rook_behind_passed_pawn_requires_open_path(self):
        open_board=chess.Board('k7/8/8/4P3/8/8/4R3/4K3 w - - 0 1')
        blocked=chess.Board('k7/8/8/4P3/8/4N3/4R3/4K3 w - - 0 1')
        names=[name for name,_ in PARAM_SPECS]
        p={name:0 for name in names};p['PAWN_VALUE']=100
        p['ROOK_BEHIND_PASSED_PAWN']=13
        baseline=dict(p);baseline['ROOK_BEHIND_PASSED_PAWN']=0
        self.assertEqual(evaluate(open_board,p)-evaluate(open_board,baseline),13)
        self.assertEqual(evaluate(blocked,p)-evaluate(blocked,baseline),0)

    def test_rook_attacks_weak_pawn_only_with_clear_file(self):
        # Black isolated pawn on a5, White rook a1; b3 blocks the rook only if on a3.
        clear=chess.Board('4k3/8/8/p7/8/8/8/R3K3 w - - 0 1')
        blocked=chess.Board('4k3/8/8/p7/8/N7/8/R3K3 w - - 0 1')
        p={name:0 for name,_ in PARAM_SPECS};p['PAWN_VALUE']=100
        p['ROOK_ATCK_WEAK_PAWN_OPEN_COLUMN']=17
        baseline=dict(p);baseline['ROOK_ATCK_WEAK_PAWN_OPEN_COLUMN']=0
        self.assertEqual(evaluate(clear,p)-evaluate(clear,baseline),17)
        self.assertEqual(evaluate(blocked,p)-evaluate(blocked,baseline),0)

if __name__=='__main__':unittest.main()
