"""Regresiones para los 35 parámetros David; ejecutar con python-chess instalado."""
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import chess
    from gen_pst_core import PARAM_SPECS, evaluate, encode_values, decode
except ImportError:
    chess = None

@unittest.skipIf(chess is None, 'requiere python-chess')
class TestDavid35(unittest.TestCase):
    def test_35_parameters_and_gray(self):
        self.assertEqual(len(PARAM_SPECS), 34)
        self.assertEqual(sum(bits for _, bits in PARAM_SPECS), 224)
        vals = [min(3, 2**bits-1) for _,bits in PARAM_SPECS]
        self.assertEqual(decode(encode_values(vals))[0].tolist(), vals)

    def test_each_missing_coefficient_affects_some_position(self):
        names = [name for name,_ in PARAM_SPECS]
        added = (
            'BACKWARD_PAWN_PENALTY','WEAK_SQUARE_PENALTY',
            'ROOK_ATTACK_KING_ADJ_FILE_ABGH','ROOK_CONNECTED',
            'ROOK_BEHIND_PASSED_PAWN','ROOK_ATCK_WEAK_PAWN_OPEN_COLUMN',
            'ROOK_COLUMN_MULT','KING_FRIENDLY_PAWN_ADVANCED1',
            'KING_NO_ENEMY_PAWN','KING_NO_ENEMY_PAWN_ADJ','KING_PRESSURE_MULT'
        )
        # Legal positions are not required to isolate every feature; FENs
        # represent well-formed arrangements with both kings present.
        fens = [
            '4k3/8/8/3pp3/4P3/8/4K3/8 w - - 0 1',
            '4k3/8/5p2/4p3/8/3P4/8/4K3 w - - 0 1',
            '4r1k1/8/8/8/8/8/8/4K3 w - - 0 1',
            'k7/8/8/8/8/8/8/1R2K3 w - - 0 1',
            '6k1/8/8/8/8/8/5P2/4K3 w - - 0 1',
            'k7/8/8/8/8/8/4K3/R6R w - - 0 1',
            'k7/8/8/4P3/8/8/4R3/4K3 w - - 0 1',
            'k7/8/8/p7/8/8/8/R3K3 w - - 0 1',
            'k7/8/8/8/4P3/8/8/4K3 w - - 0 1',
            'k7/8/8/8/8/5P2/8/4K3 w - - 0 1',
            '6k1/8/8/8/8/8/8/R3K3 w - - 0 1',
            '6k1/7p/8/8/8/8/8/4KR2 w - - 0 1',
            'k7/8/8/8/3P4/2P5/4K3/8 w - - 0 1',
            '4k3/8/8/8/8/8/8/R3K3 w - - 0 1',
        ]
        boards = [chess.Board(fen) for fen in fens]
        for name in added:
            zero = {key: 0 for key in names}
            zero['PAWN_VALUE'] = 100
            one = dict(zero)
            one[name] = 1
            self.assertTrue(any(evaluate(b, one) != evaluate(b, zero)
                                for b in boards), name)

if __name__=='__main__': unittest.main()
