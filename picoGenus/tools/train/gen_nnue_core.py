"""Value-only genetic NNUE: 768x16 + 16 bias + 16x1 + 1 = 12321 int8 genes."""
import numpy as np
from gen_common import require_chess

INPUTS = 768
HIDDEN = 16
PARAMS = INPUTS * HIDDEN + 2 * HIDDEN + 1
OUTPUT_SCALE = 256.0  # Output integers -> centipawns


def indices(board):
    """White absolute a1=0..h8=63; independent of side-to-move."""
    return np.asarray(sorted(((0 if piece.color else 6) + piece.piece_type - 1) * 64 + sq
                             for sq, piece in board.piece_map().items()), dtype=np.int32)


def padded_features(boards):
    result = np.zeros((len(boards), 32), dtype=np.int32)
    mask = np.zeros((len(boards), 32), dtype=np.int64)
    for i, board in enumerate(boards):
        active = indices(board)
        if len(active) > 32:
            raise ValueError('Tablero imposible: más de 32 piezas')
        result[i, :len(active)] = active
        mask[i, :len(active)] = 1
    return result, mask


def forward(genes, feature_indices, feature_mask):
    genes = np.asarray(genes)
    if genes.shape != (PARAMS,):
        raise ValueError(f'Formato NNUE inválido: {genes.shape}; esperado {(PARAMS,)}')
    w = genes[:INPUTS*HIDDEN].reshape(INPUTS, HIDDEN).astype(np.int32)
    bias = genes[INPUTS*HIDDEN:INPUTS*HIDDEN+HIDDEN].astype(np.int32)
    output_w = genes[INPUTS*HIDDEN+HIDDEN:-1].astype(np.int32)
    output_b = int(genes[-1])
    hidden = (w[feature_indices] * feature_mask[..., None]).sum(axis=1, dtype=np.int32) + bias
    hidden = np.clip(hidden, 0, 127)
    return ((hidden @ output_w).astype(np.float64) + output_b) / OUTPUT_SCALE


def random_genome(rng):
    return rng.integers(-15, 16, PARAMS, dtype=np.int16).astype(np.int8)


def mutate(parents, rng, rate=.02, delta=4):
    children = np.asarray(parents).copy().astype(np.int16)
    mask = rng.random(children.shape) < rate
    change = rng.integers(-delta, delta+1, size=children.shape, dtype=np.int16)
    children = np.clip(children + mask * change, -127, 127)
    return children.astype(np.int8)
