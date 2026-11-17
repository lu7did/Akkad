"""Exact GRMP0001 integer evaluator, 6-bit codec and FEN feature extraction.

Reference: picoSargon/x86/src/grumpy.cpp and Nurse _legacy/evaluators/grumpy.py.
Value returned: WHITE POV centipawns (teacher SQLite labels are STM POV).
"""
from __future__ import annotations
import hashlib
import math
import struct
from pathlib import Path

import numpy as np

MAGIC = b'GRMP0001'
N_CODES = 1680
BINARY_SIZE = 44 + 105 * 12
MATERIAL_PACKED = 0x3847D12C4B064
PIECES = 'PNBRQKpnbrqk'


def read_binary(path):
    blob = Path(path).read_bytes()
    if len(blob) != BINARY_SIZE or blob[:8] != MAGIC or struct.unpack_from('<I', blob, 8)[0] != 105:
        raise ValueError(f'Invalid GRMP0001 model: {path}')
    payload = blob[44:]
    if hashlib.sha256(payload).digest() != blob[12:44]:
        raise ValueError(f'GRMP0001 SHA256 mismatch: {path}')
    code = np.empty(N_CODES, dtype=np.int16)
    k = 0
    for i in range(0, len(payload), 12):
        x = int.from_bytes(payload[i:i+12], 'little')
        for j in range(16):
            code[k] = (x >> (j * 6) & 63) - 31
            k += 1
    return code


def write_binary(path, code):
    vals = np.asarray(code, dtype=np.int16).reshape(-1)
    if len(vals) != N_CODES or np.any(vals < -31) or np.any(vals > 32):
        raise ValueError('Model must have exactly 1680 6-bit values in [-31, 32]')
    data = bytearray()
    for start in range(0, N_CODES, 16):
        x = 0
        for j, val in enumerate(vals[start:start + 16]):
            x |= (int(val) + 31) << (6 * j)
        data.extend(x.to_bytes(12, 'little'))
    payload = bytes(data)
    blob = MAGIC + struct.pack('<I', 105) + hashlib.sha256(payload).digest() + payload
    assert len(blob) == BINARY_SIZE
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(blob)
    return blob


def feature_indexes(f):
    """GRMP separable rank/file table: two 6-bit coefficients per feature/channel."""
    base = (f // 64) * 128
    square = f % 64
    return ([base + (square // 8) * 8 + j for j in range(8)],
            [base + 64 + (square % 8) * 8 + j for j in range(8)])


def encode_fen(fen):
    parts = fen.split()
    if len(parts) < 2 or parts[1] not in ('w', 'b'):
        raise ValueError('Invalid FEN turn')
    rows = parts[0].split('/')
    if len(rows) != 8:
        raise ValueError('Invalid FEN rows')
    feats = [[], []]
    mat = 0
    count = 0
    for r, row in enumerate(rows):
        col = 0
        for c in row:
            if c.isdigit():
                n = int(c)
                if n < 1 or n > 8:raise ValueError('Invalid FEN empty count')
                col += n
                continue
            if c not in PIECES or col >= 8:raise ValueError('Invalid FEN piece')
            kind = PIECES.index(c) % 6
            sq = (7 - r) * 8 + col
            color_white = c.isupper()
            f0 = (0 if color_white else 384) + kind * 64 + sq
            f1 = ((384 if color_white else 0) + kind * 64 + sq) ^ 56
            feats[0].append(f0)
            feats[1].append(f1)
            value = (MATERIAL_PACKED >> (10 * kind)) & 1023
            mat += value if color_white else -value
            count += 1
            col += 1
        if col != 8:raise ValueError('Invalid FEN row width')
    bucket = (count - 2) // 4
    if not 0 <= bucket <= 7:raise ValueError(f'Unsupported piece count {count} (bucket {bucket})')
    if count > 32:raise ValueError('Too many pieces')
    # perspective 0 is white; perspective 1 is black; swap on black-to-move
    return (feats[0], feats[1], bucket, mat, parts[1] == 'w', count)


def eval_encoded(code, item):
    """Bit-identical white-POV integer score to the Nurse/C++ GRMP evaluator."""
    w0, w1, bucket, mat, white, _ = item
    acc = np.empty((2, 8), dtype=np.int32)
    acc[:] = np.asarray(code[1536:1544], dtype=np.int32)
    for side, features in enumerate((w0, w1)):
        for f in features:
            a, b = feature_indexes(f)
            acc[side] += code[a] + code[b]
    a, b = (acc[0], acc[1]) if white else (acc[1], acc[0])
    activation = np.maximum(0, np.minimum(32, np.concatenate((a, b))))
    total = int(8 * code[1672 + bucket] + np.dot(activation, code[1544 + 16 * bucket:1560 + 16 * bucket]))
    neural = (abs(total * 400) // 1024) * (1 if total >= 0 else -1)
    side_score = neural + (mat if white else -mat)
    return side_score if white else -side_score


def encoded_arrays(items):
    """Arrays for batched training/evaluation; -1 is padding, never a valid feature."""
    n = len(items)
    f0 = np.full((n, 32), -1, np.int64)
    f1 = np.full((n, 32), -1, np.int64)
    buckets = np.zeros(n, np.int64)
    materials = np.zeros(n, np.float32)
    turns = np.zeros(n, np.bool_)
    for i, (a, b, buck, mat, white, _) in enumerate(items):
        f0[i, :len(a)] = a
        f1[i, :len(b)] = b
        buckets[i] = buck
        materials[i] = mat
        turns[i] = white
    return f0, f1, buckets, materials, turns


def convert_teacher_cp(cp_stm, fen):
    return float(cp_stm) if fen.split()[1] == 'w' else -float(cp_stm)
