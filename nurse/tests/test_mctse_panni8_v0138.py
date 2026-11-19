"""MCTSE .bin parser, numerical parity with .pt, invalid formats, legal priors."""
import math
import pathlib
import struct
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from nurse.mcts_nnue import TinyEvaluator, PANNI8_FILE_BYTES, PANNI8_SHAPES

try:
    import torch
except ImportError:
    torch = None

class Piece:
    def __init__(self, ty, color):
        self.piece_type, self.color = ty, color

class MockBoard:
    def __init__(self, white=True):
        self.turn = white
        self.ep_square = None
    def piece_map(self):
        return {4: Piece(6, True), 60: Piece(6, False), 12: Piece(1, True), 51: Piece(1, False)}
    def has_kingside_castling_rights(self, color): return color == self.turn
    def has_queenside_castling_rights(self, color): return False

class MockMove:
    def __init__(self, src, dst):
        self.from_square, self.to_square = src, dst

@unittest.skipIf(torch is None, 'requires torch (same as existing MCTSE)')
class Panni8Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = sys.modules.get('chess')
        fake = types.ModuleType('chess')
        fake.square_rank = lambda sq: sq // 8
        fake.square_file = lambda sq: sq % 8
        sys.modules['chess'] = fake

    @classmethod
    def tearDownClass(cls):
        if cls.old is None: sys.modules.pop('chess', None)
        else: sys.modules['chess'] = cls.old

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.weights = {}
        for ix, (name, shape) in enumerate(PANNI8_SHAPES.items()):
            n = shape[0] * shape[1]
            self.weights[name] = torch.tensor([((i * (ix + 3) + 17) % 21) - 10 for i in range(n)], dtype=torch.int8).reshape(shape)
        self.scales = {'W_INPUT': 0.006, 'W_VALUE': 0.015, 'W_FROM': 0.004, 'W_TO': 0.008}
        data = bytearray(b'PANNI8\r\n' + struct.pack('<III', 1, 780, 16))
        for name in PANNI8_SHAPES: data += struct.pack('<f', self.scales[name])
        for name in PANNI8_SHAPES: data += self.weights[name].numpy().tobytes()
        self.assertEqual(len(data), PANNI8_FILE_BYTES)
        self.binfile = self.base / 'best_int8.bin'
        self.binfile.write_bytes(data)
        self.ptfile = self.base / 'best_int8.pt'
        torch.save({'format': 'picoalpha-nnue-int8-v1',
                    'config': {'features':780,'hidden':16,'policy':'from_to','value':'tanh'},
                    'weights': self.weights, 'scales': self.scales}, self.ptfile)

    def test_bin_pt_same_value_and_policy(self):
        a, b = TinyEvaluator(str(self.binfile)), TinyEvaluator(str(self.ptfile))
        for side in (True, False):
            board = MockBoard(side)
            moves = [MockMove(12, 28), MockMove(4, 6), MockMove(12, 20)]
            va, pa = a.evaluate(board, moves)
            vb, pb = b.evaluate(board, moves)
            self.assertAlmostEqual(va, vb, delta=1e-6)
            self.assertEqual(len(pa), 3)
            self.assertAlmostEqual(sum(pa.values()), 1.0, places=12)
            for ma, mb in zip(pa.values(), pb.values()):
                self.assertAlmostEqual(ma, mb, delta=1e-6)
            self.assertEqual(a.evaluate(board)[1], {})
        self.assertEqual(a.evaluations, 4)

    def test_reject_invalid_binary(self):
        with self.assertRaisesRegex(ValueError, 'tamaño'):
            bad = self.base/'truncated.bin';bad.write_bytes(b'PANNI8\r\n');TinyEvaluator(str(bad))
        data = bytearray(self.binfile.read_bytes());data[0] ^= 1
        wrong = self.base/'wrong.bin';wrong.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'cabecera'):
            TinyEvaluator(str(wrong))
        data = bytearray(self.binfile.read_bytes())
        data[20:24] = struct.pack('<f', float('nan'))
        wrong = self.base/'nan.bin';wrong.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'escalas'):
            TinyEvaluator(str(wrong))

    def test_reject_old_or_missing_extension(self):
        f=self.base/'old.bnn';f.write_bytes(b'old')
        with self.assertRaisesRegex(ValueError, 'admite solo'):
            TinyEvaluator(str(f))
        with self.assertRaisesRegex(ValueError, 'inexistente'):
            TinyEvaluator(str(self.base/'nope.bin'))

if __name__ == '__main__': unittest.main()
