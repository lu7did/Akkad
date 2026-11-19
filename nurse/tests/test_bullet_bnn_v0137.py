"""BULBNN01 Nurse regressions. Run: python -m unittest discover -s nurse/tests -p test_bullet_bnn_v0137.py"""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

# Only use a stub when python-chess is unavailable; test parser and inference anyway.
try:
    import chess
except ImportError:
    chess = types.ModuleType('chess')
    chess.WHITE, chess.BLACK = True, False
    chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING = range(1,7)
    sys.modules['chess'] = chess

SRC = Path(__file__).resolve().parents[1] / 'src' / 'nurse' / 'bullet_bnn.py'
spec = importlib.util.spec_from_file_location('bullet_bnn_under_test', SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture_bytes(sign=1):
    binary = (b'\xff' if sign == 1 else b'\x00') * mod.BINARY_BYTES
    tail = [0.0] * 97
    tail[32] = 0.75
    tail[64] = -0.5
    tail[-1] = 0.125
    payload = binary + struct.pack('<97f', *tail)
    header = b'BULBNN01' + struct.pack('<IIfI', 768, 32, 16.0, 97) + hashlib.sha256(payload).digest() + bytes(8)
    return header + payload


class Board:
    def __init__(self, black=False):
        self.turn = chess.BLACK if black else chess.WHITE
        self._pieces = {4:types.SimpleNamespace(piece_type=chess.KING,color=chess.WHITE),
                        60:types.SimpleNamespace(piece_type=chess.KING,color=chess.BLACK),
                        8:types.SimpleNamespace(piece_type=chess.PAWN,color=chess.WHITE)}
    def piece_map(self):return self._pieces
    def is_checkmate(self):return False
    def is_stalemate(self):return False
    def is_insufficient_material(self):return False
    def can_claim_draw(self):return False


class TestBulletBNN(unittest.TestCase):
    def make(self, blob):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name) / 'model.bnn'
        p.write_bytes(blob)
        return p

    def test_correct_load_and_score(self):
        ev = mod.BNNEvaluator(str(self.make(fixture_bytes())))
        self.assertEqual(ev.evaluate(Board(False)), 69)  # (0.125 + (0.75-0.5)*3/16)*400 = 68.75cp
        self.assertEqual(ev.evaluate(Board(True)), -69)
        self.assertEqual(ev.nodos_evaluados, 2)
        self.assertEqual(ev.evaluate_with_hint(Board(False)), (69, None))

    def test_wrong_magic_rejected(self):
        blob = bytearray(fixture_bytes()); blob[:8] = b'PICOBIT!'
        with self.assertRaisesRegex(ValueError, 'BULBNN01'):
            mod.BNNEvaluator(str(self.make(blob)))

    def test_corrupt_payload_rejected(self):
        blob = bytearray(fixture_bytes());blob[70] ^= 1
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            mod.BNNEvaluator(str(self.make(blob)))

    def test_truncated_rejected(self):
        with self.assertRaisesRegex(ValueError, 'tamaño'):
            mod.BNNEvaluator(str(self.make(fixture_bytes()[:-1])))

    def test_header_mismatch_rejected(self):
        blob = bytearray(fixture_bytes()); blob[12] = 31
        with self.assertRaisesRegex(ValueError, 'arquitectura'):
            mod.BNNEvaluator(str(self.make(blob)))

    def test_binary_weight_sign(self):
        plus = mod.BNNEvaluator(str(self.make(fixture_bytes(sign=1))))
        minus = mod.BNNEvaluator(str(self.make(fixture_bytes(sign=-1))))
        self.assertGreater(plus._score_features([(0,384)]), minus._score_features([(0,384)]))

if __name__ == '__main__':unittest.main()
