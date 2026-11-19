"""BULBNN01 evaluator for Nurse, Bullet BNN Genesis v0.1.0.

This format is NOT picoBit's Keras-derived .bnn/.bnni representation.
Chess768 -> 32 shared binary first-layer weights x two perspectives -> CReLU
-> 64-to-1 FP32 head; all scores are white-relative centipawns.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import struct

import chess

MAGIC = b"BULBNN01"
INPUTS = 768
HIDDEN = 32
SCALE = 16.0
TAIL = HIDDEN + HIDDEN * 2 + 1  # first-layer biases, head weights, head bias
BINARY_BYTES = INPUTS * HIDDEN // 8
HEADER_BYTES = 64
FILE_BYTES = HEADER_BYTES + BINARY_BYTES + 4 * TAIL
MATE_CP = 10000
_PIECE_TYPES = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2,
                chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
_BYTE_SIGNS = tuple(tuple(1 if b & (1 << j) else -1 for j in range(8)) for b in range(256))


def _read_bulbnn(path):
    data = Path(path).read_bytes()
    if len(data) != FILE_BYTES:
        raise ValueError(f"BULBNN01 tamaño incorrecto: {len(data)} bytes; esperados {FILE_BYTES}")
    if data[:8] != MAGIC:
        raise ValueError("BNN incompatible: se requiere BULBNN01 de Bullet; "
                         "el .bnn anterior de picoBit no es intercambiable")
    inputs, hidden, scale, tail = struct.unpack_from('<IIfI', data, 8)
    if (inputs, hidden, scale, tail) != (INPUTS, HIDDEN, SCALE, TAIL):
        raise ValueError(f"BULBNN01 arquitectura inválida: {(inputs, hidden, scale, tail)}")
    if data[56:64] != b'\x00' * 8:
        raise ValueError("BULBNN01 cabecera reservada inválida")
    if hashlib.sha256(data[HEADER_BYTES:]).digest() != data[24:56]:
        raise ValueError("BULBNN01 SHA-256 del payload incorrecto")
    params = struct.unpack_from('<97f', data, HEADER_BYTES + BINARY_BYTES)
    if not all(math.isfinite(v) for v in params):
        raise ValueError("BULBNN01 contiene sesgos/pesos FP32 no finitos")
    return bytes(data[HEADER_BYTES:HEADER_BYTES + BINARY_BYTES]), params


class BNNEvaluator:
    """Nurse evaluator. Chess score perspective: positive favors WHITE."""
    name = 'BNN'
    trainable = False

    def __init__(self, network):
        if not network:
            raise ValueError('BNN requiere evaluator.network apuntando a BULBNN01 .bnn')
        path = Path(network).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f'BNN Bullet inexistente: {path}')
        self._bits, tail = _read_bulbnn(path)
        self._bias0 = tail[:HIDDEN]
        self._head = tail[HIDDEN:HIDDEN + 2 * HIDDEN]
        self._bias1 = tail[-1]
        self.source = str(path)
        self.native = self.source
        self.nodos_evaluados = 0

    def _score_features(self, features):
        """Exact first-layer bit decoding and CReLU; STM/NTM normalized features.

        Each pair is (stm_feature, ntm_feature), matching Bullet Chess768.
        """
        accum = [list(self._bias0), list(self._bias0)]
        bits = self._bits
        for stm, ntm in features:
            for side, feature in ((0, stm), (1, ntm)):
                if not (0 <= feature < INPUTS):
                    raise ValueError(f'Chess768 feature inválida: {feature}')
                dst = accum[side]
                offset = feature * (HIDDEN // 8)
                for group in range(HIDDEN // 8):
                    signs = _BYTE_SIGNS[bits[offset + group]]
                    k = group * 8
                    for j in range(8):
                        dst[k+j] += signs[j] / SCALE
        score = float(self._bias1)
        for side in range(2):
            for j in range(HIDDEN):
                score += min(1.0, max(0.0, accum[side][j])) * self._head[side*HIDDEN+j]
        return score * 400.0

    def evaluate(self, board):
        self.nodos_evaluados += 1
        if board.is_checkmate():
            return -MATE_CP if board.turn == chess.WHITE else MATE_CP
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0
        turn_black = board.turn == chess.BLACK
        features = []
        for square, piece in board.piece_map().items():
            kind = _PIECE_TYPES[piece.piece_type]
            # Match Bullet bnn_export.py: transformed square and side-relative colors.
            c_black = (piece.color == chess.BLACK) != turn_black
            sq = square ^ (56 if turn_black else 0)
            base = 64 * kind
            stm = (384 if c_black else 0) + base + sq
            ntm = (0 if c_black else 384) + base + (sq ^ 56)
            features.append((stm, ntm))
        cp = self._score_features(features) * (-1.0 if turn_black else 1.0)
        if not math.isfinite(cp):
            raise ValueError('BNN devolvió evaluación no finita')
        return int(round(cp))

    def evaluate_with_hint(self, board, *, incremental=False, previous_state=None):
        return self.evaluate(board), None

    def close(self):
        pass
