"""picoBit BNN integration and perspective regression tests."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

# Offline CI fallback for environments without python-chess. Real deployments
# use python-chess; these tests only validate tensor encoding and perspective.
try:
    import chess
    _CHESS_STUB = False
except ImportError:
    _CHESS_STUB = True
    import types
    chess = types.ModuleType('chess')
    chess.WHITE = True
    chess.BLACK = False
    chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING = range(1, 7)
    chess.STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
    class Piece:
        def __init__(self, piece_type, color):
            self.piece_type, self.color = piece_type, color
    class Board:
        def __init__(self, fen=chess.STARTING_FEN):
            self._fen = fen
            piece_types = {'p':1,'n':2,'b':3,'r':4,'q':5,'k':6}
            self._pieces = {}
            parts = fen.split()
            self.turn = parts[1] == 'w'
            for row, rank in enumerate(reversed(parts[0].split('/'))):
                col = 0
                for letter in rank:
                    if letter.isdigit():col += int(letter)
                    else:
                        self._pieces[row*8+col] = Piece(piece_types[letter.lower()], letter.isupper());col+=1
        def fen(self): return self._fen
        def piece_map(self): return self._pieces
        def is_checkmate(self):
            return (self._fen.startswith('7k/8/8/8/8/8/6q1/7K') or
                    self._fen.startswith('7k/6Q1/6K1/8/8/8/8/8'))
        def is_stalemate(self):return False
        def is_insufficient_material(self):return len(self._pieces)<=2
        def can_claim_draw(self):return False
    chess.Board = Board
    sys_modules = __import__('sys').modules
    sys_modules['chess'] = chess
from unittest.mock import MagicMock, patch

NURSE_ROOT = Path(__file__).resolve().parents[1]
AKKAD_ROOT = NURSE_ROOT.parent
sys.path.insert(0, str(NURSE_ROOT / 'src'))
from nurse import engine_registry
from nurse.bnn_eval import _implementation, make_bnn


class PicoBitBNNTest(unittest.TestCase):
    def test_registry(self):
        self.assertIn('bnn', engine_registry.choices('evaluator'))
        for player in ('sargon', 'sargon-plus', 'doc'):
            engine_registry.ensure_pair(player, 'bnn', nurse_only=True)
        self.assertTrue(engine_registry.source('evaluator', 'bnn').endswith('evaluators/bnn.py'))

    def test_factory_requires_network(self):
        with self.assertRaisesRegex(ValueError, 'network'):
            make_bnn()

    def test_input_channels_and_stm_no_mirroring(self):
        import chess
        core = _implementation()
        white = chess.Board()
        black = chess.Board(white.fen().replace(' w ', ' b ', 1))
        xw = core.board_tensor(white)
        xb = core.board_tensor(black)
        self.assertEqual(xw.shape, (1, 8, 8, 13))
        self.assertEqual(float(xw[0, 0, 0, 3]), 1.0) # a1 white rook
        self.assertEqual(float(xw[0, 7, 4, 11]), 1.0) # e8 black king
        self.assertEqual(float(xw[0, 1, 4, 0]), 1.0) # e2 white pawn
        self.assertTrue((xw[0, :, :, :12] == xb[0, :, :, :12]).all())
        self.assertTrue((xw[0, :, :, 12] == 1).all())
        self.assertTrue((xb[0, :, :, 12] == -1).all())

    def test_probability_white_relative(self):
        core = _implementation()
        self.assertEqual(core.probability_to_white_cp(.5), 0)
        self.assertEqual(core.probability_to_white_cp(.9), 382)
        self.assertEqual(core.probability_to_white_cp(.1), -382)
        self.assertEqual(core.probability_to_white_cp(1.0), 1600)
        with self.assertRaisesRegex(ValueError, 'intervalo'):
            core.probability_to_white_cp(1.4)

    def test_terminal_sign_even_without_model(self):
        import chess
        core = _implementation()
        eval_obj = core.BNNEvaluator.__new__(core.BNNEvaluator)
        eval_obj.nodos_evaluados = 0
        eval_obj.tf = MagicMock()
        eval_obj._infer = MagicMock(return_value=[[.9]])
        checkmated_white = chess.Board('7k/8/8/8/8/8/6q1/7K w - - 0 1')
        self.assertEqual(eval_obj.evaluate(checkmated_white), -10000)
        checkmated_black = chess.Board('7k/6Q1/6K1/8/8/8/8/8 b - - 0 1')
        self.assertEqual(eval_obj.evaluate(checkmated_black), 10000)
        self.assertEqual(eval_obj.evaluate(chess.Board('8/8/8/8/8/8/8/K6k w - - 0 1')), 0)

    @unittest.skipIf(_CHESS_STUB, "requiere python-chess real para importar evaluadores legados")
    def test_legacy_factory_uses_registry_factory(self):
        from nurse._legacy.evaluators import create_evaluator
        import chess
        with patch('nurse.bnn_eval.make_bnn') as mocked:
            result = create_evaluator('bnn', 'example.keras')
            self.assertIs(result, mocked.return_value)
            mocked.assert_called_once()
            self.assertEqual(mocked.call_args.kwargs['network'], 'example.keras')

    def test_factory_end_to_end_with_mock_model(self):
        import chess
        core = _implementation()
        with tempfile.TemporaryDirectory() as tmp:
            weights = Path(tmp) / 'test.keras'
            weights.write_bytes(b'placeholder')
            fake_model = MagicMock()
            fake_model.input_shape = (None, 8, 8, 13)
            fake_model.output_shape = (None, 1)
            mock_tf = MagicMock()
            mock_tf.keras.models.load_model.return_value = fake_model
            mock_tf.function.side_effect = lambda fn, **kw: fn
            mock_tf.convert_to_tensor.side_effect = lambda x: x
            fake_model.return_value = [[.9]]
            with patch.dict(sys.modules, {'tensorflow': mock_tf}):
                evaluator = make_bnn(str(weights))
                self.assertEqual(evaluator.evaluate(chess.Board()), 382)
                board_black = chess.Board(chess.Board().fen().replace(' w ', ' b ', 1))
                self.assertEqual(evaluator.evaluate(board_black), 382)
                self.assertEqual(evaluator.evaluate_with_hint(board_black)[0], 382)
                self.assertEqual(evaluator.nodos_evaluados, 3)
                evaluator.close()


if __name__ == '__main__': unittest.main()
