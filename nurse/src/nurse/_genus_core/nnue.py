"""GENUS tiny NNUE 768 -> 16 ClippedReLU -> 1, white-perspective cp.

FP32 inference matches picoGen/tools/train/gen_fp32_core.py exactly.
Legacy int16 (unscaled) and int8 (/256) remain supported without conversion.
"""
import numpy as np

INPUTS = 768
HIDDEN = 16
PARAMS = INPUTS * HIDDEN + HIDDEN + HIDDEN + 1
OUTPUT_SCALE = 1.0


def indices(board):
    return np.asarray(sorted(((0 if piece.color else 6) + piece.piece_type - 1) * 64 + sq
                             for sq, piece in board.piece_map().items()), dtype=np.int32)


def padded_features(boards):
    x = np.zeros((len(boards), 32), dtype=np.int32)
    mask = np.zeros((len(boards), 32), dtype=np.int64)
    for i, board in enumerate(boards):
        active = indices(board)
        if len(active) > 32:
            raise ValueError('Más de 32 piezas')
        x[i, :len(active)] = active
        mask[i, :len(active)] = 1
    return x, mask


def hidden_activations(genes, x, mask, clip_max=127):
    genes = np.asarray(genes)
    if genes.shape != (PARAMS,):
        raise ValueError('Vector NNUE de dimensión incorrecta')
    if genes.dtype == np.dtype('float32'):
        w = genes[:INPUTS * HIDDEN].reshape(INPUTS, HIDDEN)
        bias = genes[INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN]
        raw = (w[x] * mask[..., None]).sum(axis=1, dtype=np.float32) + bias
        return np.clip(raw, 0.0, float(clip_max))
    if genes.dtype not in (np.dtype('int16'), np.dtype('int8')):
        raise ValueError(f'NNUE dtype incompatible: {genes.dtype}; expected float32, int16 or int8')
    w = genes[:INPUTS * HIDDEN].reshape(INPUTS, HIDDEN).astype(np.int64)
    bias = genes[INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN].astype(np.int64)
    raw = (w[x] * mask[..., None]).sum(axis=1, dtype=np.int64) + bias
    return np.clip(raw, 0, 127)


def forward(genes, x, mask, clip_max=127):
    genes = np.asarray(genes)
    hidden = hidden_activations(genes, x, mask, clip_max=clip_max)
    if genes.dtype == np.dtype('float32'):
        # No integer conversion: same operations/order and float32 accumulation as picoGen.
        value = hidden @ genes[INPUTS * HIDDEN + HIDDEN:-1] + genes[-1]
        return value.astype(np.float64)
    w2 = genes[INPUTS * HIDDEN + HIDDEN:-1].astype(np.int64)
    b2 = int(genes[-1])
    result = (hidden @ w2).astype(np.float64) + b2
    if genes.dtype == np.dtype('int8'):
        return result / 256.0
    if genes.dtype != np.dtype('int16'):
        raise ValueError(f'NNUE dtype incompatible: {genes.dtype}; expected float32, int16 or legacy int8')
    return result


def random_genome(rng):
    # Legacy helper kept intact; new FP32 training happens in picoGen.
    return rng.integers(-15, 16, size=PARAMS, dtype=np.int16)


def mutate(parent, rng, rate=.03, delta=6, return_count=False):
    # Legacy helper kept intact; no mutation occurs in Nurse inference.
    parent = np.asarray(parent, dtype=np.int16)
    mask = rng.random(PARAMS) < rate
    changes = rng.integers(-delta, delta + 1, size=PARAMS)
    child = np.clip(parent.astype(np.int64) + (mask * changes), -127, 127).astype(np.int16)
    if return_count:
        return child, int(np.count_nonzero(child != parent))
    return child
