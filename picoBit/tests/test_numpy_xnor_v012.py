"""v0.1.12 regression: compare vectorized XNOR and folded fixed-point inference
with a straightforward 9-tap packed reference, and print isolated latency.
Does not require TensorFlow or python-chess; requires NumPy and h5py for fixture.
"""
import sys
from pathlib import Path
import tempfile
import time
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_numpy_equivalence import fake_checkpoint, engine


def reference(e, piece, turn):
    side = 1 if turn else -1
    dots = np.zeros((64, 64), dtype=np.int16)
    for kr in range(3):
        for kc in range(3):
            k = kr * 3 + kc
            for sq in range(64):
                row, col = divmod(sq, 8)
                nr, nc = row + kr - 1, col + kc - 1
                if not (0 <= nr < 8 and 0 <= nc < 8):
                    continue
                p = int(piece[nr * 8 + nc])
                dots[sq] += e._piece_signs[k, p]
                dots[sq] += side * e._turn_signs[k]
    a1 = dots.astype(np.int64) * e.s1 + e.b1
    bits = np.packbits(a1 >= 0, axis=1, bitorder='little').view('<u8').reshape(64)
    dots2 = np.zeros((64, 64), dtype=np.int16)
    for kr in range(3):
        for kc in range(3):
            k = kr * 3 + kc
            for sq in range(64):
                row, col = divmod(sq, 8)
                nr, nc = row + kr - 1, col + kc - 1
                if not (0 <= nr < 8 and 0 <= nc < 8):
                    continue
                v = int(bits[nr * 8 + nc])
                dots2[sq] += np.array([2 * ((~(v ^ int(w))) & ((1 << 64) - 1)).bit_count() - 64
                                       for w in e.w2[k]], dtype=np.int16)
    a2 = dots2.astype(np.int64) * e.s2 + e.b2 + a1
    dense = np.packbits(a2 >= 0, axis=1, bitorder='little').view('<u8').reshape(64)
    sums = np.array([sum(2 * ((~(int(w) ^ int(x))) & ((1 << 64) - 1)).bit_count() - 64
                         for w, x in zip(row, dense)) for row in e.wd], dtype=np.int64)
    cp = int(e.b3) + sum(int(v) * int(c) for v, c in zip(sums, e.s3))
    cp = max(-1600 * (1 << 20), min(1600 * (1 << 20), cp))
    q = 1 << 20
    return (cp + q//2)//q if cp >= 0 else -((-cp + q//2)//q)


def main():
    with tempfile.TemporaryDirectory() as d:
        filename = Path(d) / 'fixture.bnn'
        fake_checkpoint(filename, seed=123)
        evaluator = engine.BNNEvaluator(str(filename))
        rng = np.random.default_rng(3221)
        cases = []
        for i in range(40):
            board = np.zeros(64, dtype=np.uint8)
            n = int(rng.integers(0, 43))
            indexes = rng.choice(64, size=n, replace=False)
            board[indexes] = rng.integers(1, 13, size=n)
            turn = bool(rng.integers(0, 2))
            cases.append((board, turn))
            actual = evaluator._eval_squares(board, turn)
            expected = reference(evaluator, board, turn)
            assert actual == expected, (i, actual, expected)
        for _ in range(20):
            evaluator._eval_squares(*cases[0])
        start = time.perf_counter()
        for _ in range(10):
            for board, turn in cases:
                evaluator._eval_squares(board, turn)
        dt = time.perf_counter() - start
        print(f'PASS: {len(cases)} reference comparisons, 0 cp difference; '
              f'isolated NumPy {len(cases)*10/dt:.0f} eval/s ({1000*dt/(len(cases)*10):.3f} ms/eval)')

if __name__ == '__main__':
    main()
