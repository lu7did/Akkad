"""Pure NumPy inference for picoGen GRMP0001-192x8-dual-8bucket FP32.

Implements gen_grumpy_pgpe_core.from_board/forward without torch or picoGen at
runtime. Returns WHITE-perspective centipawns, including Grumpy fixed material.
"""
from __future__ import annotations
import numpy as np

GENES = 1680
FORMAT = 'picogen-grumpy-pgpe-fp32-v1'
ARCHITECTURE = 'GRMP0001-192x8-dual-8bucket-fp32'
MATERIAL = (100, 300, 300, 500, 900, 0)
CP_SCALE = 400.0 / 1024.0


def validate_manifest(meta):
    if not isinstance(meta, dict) or meta.get('format') != FORMAT:
        raise ValueError('Grumpy FP32: invalid manifest format')
    if (meta.get('dtype') != 'float32' or meta.get('genes') != GENES or
            meta.get('architecture') != ARCHITECTURE or
            meta.get('hidden_clip') != 32 or
            meta.get('fixed_material') != list(MATERIAL) or
            meta.get('output_scale') != 1):
        raise ValueError('Grumpy FP32: incompatible architecture/material/scale manifest')


def _factor_index(feature):
    group, square = divmod(int(feature), 64)
    return group * 16 + square // 8, group * 16 + 8 + square % 8


def board_features(board):
    """Same factor indices, STM swap, material and output bucket as picoGen."""
    import chess
    pieces = list(board.piece_map().items())
    if not 2 <= len(pieces) <= 32:
        raise ValueError('Grumpy FP32 supports 2..32 pieces')
    x = np.zeros((2, 64), dtype=np.int64)
    material = 0
    for index, (square, piece) in enumerate(pieces):
        kind = piece.piece_type - 1
        material += MATERIAL[kind] * (1 if piece.color == chess.WHITE else -1)
        f0 = (0 if piece.color == chess.WHITE else 384) + kind * 64 + square
        f1 = ((384 if piece.color == chess.WHITE else 0) + kind * 64 + square) ^ 56
        for perspective, feature in enumerate((f0, f1)):
            a, b = _factor_index(feature)
            x[perspective, 2 * index] = a
            x[perspective, 2 * index + 1] = b
    if board.turn == chess.BLACK:
        x = x[::-1].copy()
    return x, 2 * len(pieces), (len(pieces)-2)//4, float(material), (1 if board.turn == chess.WHITE else -1)


def forward_features(weights, features):
    """Evaluate pre-extracted Grumpy features; preserves FP32 training arithmetic."""
    w = np.asarray(weights)
    if w.shape != (GENES,) or w.dtype != np.float32 or not np.isfinite(w).all():
        raise ValueError('Grumpy FP32 requires 1680 finite float32 weights')
    x, count, bucket, material, stm_sign = features
    if not 0 <= bucket < 8 or not 4 <= count <= 64 or count % 2:
        raise ValueError('Invalid Grumpy piece count/bucket')
    factors = w[:1536].reshape(192, 8)
    bias = w[1536:1544]
    out = w[1544:1672].reshape(8, 16)
    out_bias = w[1672:1680]
    # Accumulate in float32, exactly like torch's weighted gather/reduction.
    a = np.clip(factors[np.asarray(x[0, :count], dtype=np.int64)].sum(axis=0, dtype=np.float32) + bias, 0.0, 32.0)
    b = np.clip(factors[np.asarray(x[1, :count], dtype=np.int64)].sum(axis=0, dtype=np.float32) + bias, 0.0, 32.0)
    hidden = np.concatenate((a, b))
    residual = np.sum(hidden * out[bucket], dtype=np.float32) + np.float32(8.0) * out_bias[bucket]
    score = np.float32(material) + np.float32(stm_sign) * np.float32(CP_SCALE) * residual
    if not np.isfinite(score):
        raise ValueError('Grumpy FP32 produced nonfinite evaluation')
    return float(score)


def evaluate_board(weights, board):
    return forward_features(weights, board_features(board))
