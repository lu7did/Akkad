"""Inference for the original LNNUE v1 768-32-1 quantized network.

This is NOT the later Luminex HalfKA network family (.nnue).
Returns WHITE-perspective centipawns for Nurse.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path

class EvaluatorError(ValueError):
    """Invalid Luminex model or configuration."""


class Evaluator:
    """Minimal implementation of Nurse evaluator interface."""
    def close(self):
        pass

    def reload(self):
        pass

MAGIC = b'LNNUE'
HEADER = struct.Struct('<5s5i')
INPUTS, HIDDEN = 768, 32
EXPECTED_SIZE = HEADER.size + 2 * (INPUTS * HIDDEN + HIDDEN + HIDDEN + 1)
# cp = 200 * log(p / (1-p)): zero at 0.5; increasing and antisymmetric.
# The conversion is a configurable modelling convention, NOT learned calibration.
DEFAULT_CP_PER_LOG_ODDS = 200.0
EPS = 1e-6


class LuminexEvaluator(Evaluator):
    name = 'LUMINEX'
    trainable = False

    def __init__(self, network: str, *, cp_per_log_odds: float = DEFAULT_CP_PER_LOG_ODDS):
        if not isinstance(network, (str, Path)) or not str(network):
            raise EvaluatorError('luminex requiere evaluator.network (.bin LNNUE v1)')
        if not isinstance(cp_per_log_odds, (float, int)) or isinstance(cp_per_log_odds, bool) or not math.isfinite(cp_per_log_odds) or cp_per_log_odds <= 0:
            raise EvaluatorError('cp_per_log_odds debe ser un número finito positivo')
        self.cp_per_log_odds = float(cp_per_log_odds)
        self.path = Path(network)
        data = self.path.read_bytes()
        if len(data) != EXPECTED_SIZE:
            raise EvaluatorError(f'LNNUE v1: tamaño incorrecto: {len(data)} bytes (esperado {EXPECTED_SIZE})')
        magic, version, inputs, hidden, l1_scale, out_scale = HEADER.unpack_from(data)
        if (magic, version, inputs, hidden) != (MAGIC, 1, INPUTS, HIDDEN):
            raise EvaluatorError(f'cabecera LNNUE incompatible: magic={magic!r}, version={version}, shape={inputs}->{hidden}')
        if (l1_scale, out_scale) != (255, 64):
            raise EvaluatorError(f'escalas LNNUE no soportadas: {l1_scale}/{out_scale} (esperadas 255/64)')
        self.l1_scale = l1_scale
        self.out_scale = out_scale
        values = struct.unpack_from('<' + 'h' * (INPUTS * HIDDEN + HIDDEN + HIDDEN + 1), data, HEADER.size)
        offset = INPUTS * HIDDEN
        self.weights = tuple(values[i * INPUTS:(i + 1) * INPUTS] for i in range(HIDDEN))
        self.bias = values[offset:offset + HIDDEN]
        self.output_weights = values[offset + HIDDEN:offset + HIDDEN + HIDDEN]
        self.output_bias = values[-1]

    @staticmethod
    def active_features(board):
        # Canonical Chess768 ordering: white P,N,B,R,Q,K then black P,N,B,R,Q,K,
        # each square indexed a1=0..h8=63. Does not encode side-to-move.
        import chess
        for color, color_offset in ((chess.WHITE, 0), (chess.BLACK, 6)):
            for piece_type in range(chess.PAWN, chess.KING + 1):
                base = (color_offset + piece_type - 1) * 64
                for square in chess.scan_forward(board.pieces_mask(piece_type, color)):
                    yield base + square

    def probability(self, board) -> float:
        features = tuple(self.active_features(board))
        # Dequantized clipped ReLU for each of the 32 hidden channels.
        # Quantizer convention: weights and first biases /255; output weights
        # and output bias /64. No scipy/torch dependency.
        acc = 0.0
        for i in range(HIDDEN):
            row = self.weights[i]
            activation = (self.bias[i] + sum(row[index] for index in features)) / self.l1_scale
            activation = min(1.0, max(0.0, activation))
            acc += self.output_weights[i] * activation
        logit = (self.output_bias + acc) / self.out_scale
        if logit >= 0:
            return 1.0 / (1.0 + math.exp(-logit))
        exp_logit = math.exp(logit)
        return exp_logit / (1.0 + exp_logit)

    def evaluate(self, board) -> int:
        p = min(1.0 - EPS, max(EPS, self.probability(board)))
        return round(self.cp_per_log_odds * math.log(p / (1.0 - p)))


def make_luminex(*, network=None, **kwargs):
    if not network:
        raise EvaluatorError('luminex requiere evaluator.network')
    return LuminexEvaluator(network)
