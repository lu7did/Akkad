"""Bullet Chess768 NNUE FP32 inference, compatible with Nurse's white-relative cp.

Model: two shared 768x128 affine perspectives -> SCReLU -> 256x1.
Matches Bullet commit 5d701776 and picoBit picobit-nnue-003-100/raw.bin.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import chess
import numpy as np

INPUTS = 768
HIDDEN = 128
PARAMS = INPUTS * HIDDEN + HIDDEN + 2 * HIDDEN + 1
MODEL_BYTES = PARAMS * 4
EVAL_SCALE = 400.0


class BulletEvaluator:
    """Unquantised Bullet raw.bin evaluator, white-perspective centipawns."""

    name = 'BULLET'
    trainable = False

    def __init__(self, network: str):
        if not network:
            raise ValueError('bullet requiere evaluator.network con raw.bin')
        source = Path(network).expanduser().resolve(strict=True)
        if source.suffix.lower() != '.bin':
            raise ValueError('bullet requiere un raw.bin FP32, no quantised.bin')
        if source.name != 'raw.bin':
            raise ValueError('bullet requiere el archivo raw.bin de Bullet')
        data = source.read_bytes()
        if len(data) != MODEL_BYTES:
            raise ValueError(f'Bullet raw.bin incompatible: {len(data)} bytes; se esperan {MODEL_BYTES}')
        weights = np.frombuffer(data, dtype='<f4').copy()
        if not np.all(np.isfinite(weights)):
            raise ValueError('Bullet raw.bin contiene pesos no finitos')
        cursor = INPUTS * HIDDEN
        # Bullet l0w is feature-major: [feature, hidden] not [hidden, feature].
        self.w0 = weights[:cursor].reshape(INPUTS, HIDDEN)
        self.b0 = weights[cursor:cursor + HIDDEN]
        cursor += HIDDEN
        self.w1 = weights[cursor:cursor + 2 * HIDDEN]
        cursor += 2 * HIDDEN
        self.b1 = float(weights[cursor])
        for a in (self.w0, self.b0, self.w1):
            a.flags.writeable = False
        self.source = str(source)
        self.sha256 = hashlib.sha256(data).hexdigest()

    @staticmethod
    def features(board: chess.Board) -> tuple[list[int], list[int]]:
        """Exact Chess768 mapping using BulletFormat's STM-normalised board.

        Piece IDs P,N,B,R,Q,K = 0..5; our side first, their side +384.
        Squares are flipped vertically when black is to move. The NTM
        perspective flips squares again and exchanges colour offsets.
        """
        if not board.is_valid():
            raise ValueError('FEN contiene una posición de ajedrez inválida')
        black_to_move = board.turn == chess.BLACK
        stm, ntm = [], []
        for square, piece in board.piece_map().items():
            pc = 64 * (piece.piece_type - 1)
            c = piece.color != board.turn  # opponent=1, us=0
            sq = square ^ (56 if black_to_move else 0)
            stm.append((384 if c else 0) + pc + sq)
            ntm.append((0 if c else 384) + pc + (sq ^ 56))
        return stm, ntm

    def raw(self, board: chess.Board) -> float:
        """Raw pre-sigmoid logit, positive for the side to move."""
        stm, ntm = self.features(board)
        # Sum in float32, as in native inference, and apply SCReLU.
        a = self.b0 + np.sum(self.w0[stm], axis=0, dtype=np.float32)
        b = self.b0 + np.sum(self.w0[ntm], axis=0, dtype=np.float32)
        a = np.square(np.clip(a, 0.0, 1.0))
        b = np.square(np.clip(b, 0.0, 1.0))
        out = (np.dot(a, self.w1[:HIDDEN]) +
               np.dot(b, self.w1[HIDDEN:]) + self.b1)
        return float(out)

    def probability(self, board: chess.Board) -> float:
        """Sigmoid of the raw logit, side-to-move expected score."""
        import math
        z = self.raw(board)
        return 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))

    def evaluate(self, board: chess.Board) -> int:
        """White-relative centipawns for Nurse's Sargon-Plus evaluator API."""
        score = self.raw(board) * EVAL_SCALE
        if board.turn == chess.BLACK:
            score = -score
        return int(round(score))

    def evaluate_with_hint(self, board, *, incremental=False, previous_state=None):
        return self.evaluate(board), None

    def close(self):
        pass


def make_bullet(network=None, **_kwargs):
    return BulletEvaluator(network)
