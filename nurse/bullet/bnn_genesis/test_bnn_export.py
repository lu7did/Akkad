import hashlib
import math
import random
import tempfile
import unittest
from pathlib import Path

from bnn_export import ALL, INPUTS, HIDDEN, SIZE, WEIGHTS, decode, encode, score_fen


class BnnFormatTests(unittest.TestCase):
    def test_roundtrip_and_hash(self):
        rng = random.Random(1937)
        w = [rng.uniform(-0.7, 0.7) for _ in range(ALL)]
        blob = encode(w)
        self.assertEqual(len(blob), SIZE)
        recovered = decode(blob)
        self.assertEqual(recovered[:WEIGHTS], [1.0 if x >= 0 else -1.0 for x in w[:WEIGHTS]])
        self.assertTrue(all(abs(x-y) < 1e-6 for x, y in zip(recovered[WEIGHTS:], w[WEIGHTS:])))
        bad = bytearray(blob)
        bad[-1] ^= 1
        with self.assertRaises(ValueError):
            decode(bytes(bad))

    def test_fen_score_and_turn(self):
        w = [-1.0] * WEIGHTS + [0.0] * (HIDDEN + HIDDEN*2 + 1)
        # zero biases and head -> exactly zero for any legal position
        for turn in ['w', 'b']:
            fen = f'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR {turn} KQkq - 0 1'
            self.assertEqual(score_fen(fen, w), 0.0)

    def test_reject_nan(self):
        w = [0.0]*ALL
        w[0] = math.nan
        with self.assertRaises(ValueError): encode(w)


if __name__ == '__main__': unittest.main()
