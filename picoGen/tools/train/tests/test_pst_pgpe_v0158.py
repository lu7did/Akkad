"""Run: python -m unittest discover -s picoGen/tools/train/tests -p test_pst_pgpe_v0158.py"""
import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import chess
import gen_pst_pgpe_core as g
from gen_fp32_core import pst_evaluate

class PGPEPST(unittest.TestCase):
    def test_material_is_evolvable_and_scale_fixed(self):
        self.assertIn('PAWN_VALUE',g.NAMES)
        self.assertNotIn('CALIBRATION_SCALE',g.NAMES)
        p=g.params(g.BASE)
        self.assertEqual(p['PAWN_VALUE'],100)
        self.assertEqual(p['KNIGHT_VALUE'],300)
        self.assertEqual(p['BISHOP_VALUE'],300)
        self.assertEqual(p['ROOK_VALUE'],500)
        self.assertEqual(p['QUEEN_VALUE'],900)
        self.assertEqual(p['CALIBRATION_SCALE'],100)
        candidate=np.zeros(len(g.NAMES),np.float32)
        candidate[g.NAMES.index('PAWN_VALUE')]=1
        self.assertGreater(g.decode(candidate)[g.NAMES.index('PAWN_VALUE')],100)
        self.assertEqual(g.params(g.decode(candidate))['CALIBRATION_SCALE'],100)

    def test_features_exact_reference(self):
        board=chess.Board()
        scenarios=[board.copy()]
        for uci in ['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4','g8f6']:
            board.push_uci(uci);scenarios.append(board.copy())
        # Decisive material differences, castling and isolated pawns.
        for f in ['4k3/8/8/8/8/8/4P3/4K3 w - - 0 1',
                  '4k3/8/8/8/8/8/8/4K3 w - - 0 1',
                  'r3k2r/pppp1ppp/8/8/8/8/PPPP1PPP/R3K2R b KQkq - 0 1']:
            b=chess.Board(f)
            if b.is_valid():scenarios.append(b)
        for b in scenarios:
            x,override=g.features(b)
            g.verify([(b,x,override)])
            for factor in (.5,1.0,1.5):
                w=g.BASE.copy()
                w[g.NAMES.index('PAWN_VALUE')]*=factor
                y=float(override) if np.isfinite(override) else float(np.clip(x.astype(float)@w.astype(float),-2000,2000))
                expected=pst_evaluate(b,g.params(w))
                self.assertAlmostEqual(y,expected,delta=.005,msg=b.fen())

    def test_batch_mse_correct(self):
        x=np.array([[1.,-1.],[-2.,2.]],np.float32)
        y=np.array([100.,-100.])
        w=np.array([[100.,0.],[0.,100.]],np.float32)
        p=g.forward(x,np.array([np.nan,np.nan]),w)
        self.assertEqual(p.shape,(2,2))
        np.testing.assert_allclose(p,np.array([[100.,-100.],[-200.,200.]]))
        p2=g.forward(x,np.array([2000.,np.nan]),w)
        np.testing.assert_allclose(p2[0],np.array([2000.,2000.]))

if __name__=='__main__':unittest.main()
