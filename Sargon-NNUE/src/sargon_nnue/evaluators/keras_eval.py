"""Evaluador Searchless basado en TensorFlow SavedModel nativo (no TFLite)."""
from __future__ import annotations
import math
from pathlib import Path
import chess
import numpy as np
from .base import Evaluator, EvaluatorError

CHANNELS = {(ptype, color): ptype - 1 + (0 if color == chess.WHITE else 6)
            for color in (chess.WHITE, chess.BLACK) for ptype in range(1, 7)}

def board_tensor(board: chess.Board):
    b = board.mirror() if board.turn == chess.BLACK else board
    arr = np.zeros((8, 8, 12), dtype=np.uint8)
    for square, piece in b.piece_map().items():
        rank, file = divmod(square, 8)
        arr[7-rank, file, CHANNELS[(piece.piece_type, piece.color)]] = 1
    return arr

def normalized_to_cp(value):
    v = float(value)
    if not math.isfinite(v): raise EvaluatorError('salida Keras no finita')
    if v >= .999: return 10000
    if v <= -.999: return -10000
    return int(round(math.log((1. + v) / (1. - v)) / .00368208))

class KerasEvaluator(Evaluator):
    name = 'KERAS'
    def __init__(self, network: str):
        p = Path(network).expanduser().resolve()
        if not p.is_dir() or not (p / 'saved_model.pb').is_file():
            raise EvaluatorError(f'network keras requiere directorio TensorFlow SavedModel: {p}')
        try:
            import tensorflow as tf
            self.tf = tf
            module = tf.saved_model.load(str(p))
            signatures = module.signatures
            self.fn = signatures.get('serve')
            if self.fn is None: self.fn = signatures.get('serving_default')
            if self.fn is None: raise EvaluatorError(f'SavedModel sin firma serve/serving_default: {p}')
            args, kwargs = self.fn.structured_input_signature
            if len(kwargs) == 1:
                self.input_name, spec = next(iter(kwargs.items()))
            elif len(args) == 1:
                self.input_name, spec = None, args[0]
            else:
                raise EvaluatorError(f'firma de entrada incompatible: args={args}, kwargs={kwargs}')
            shape = tuple(spec.shape.as_list())
            if len(shape) != 4 or shape[1:] != (8, 8, 12) or shape[0] not in (1, None):
                raise EvaluatorError(f'input inesperado: {shape}; esperado (None,8,8,12)')
            self.dtype = spec.dtype
            self.fixed_batch_one = shape[0] == 1
            if not self.dtype.is_floating and not self.dtype.is_integer:
                raise EvaluatorError(f'tipo de entrada incompatible: {self.dtype}')
        except EvaluatorError: raise
        except Exception as exc: raise EvaluatorError(f'no se pudo cargar SavedModel TensorFlow: {exc}') from exc
    def evaluate_batch(self, boards):
        """Return WHITE-relative centipawns, one value per board."""
        from ..types import MATE_CP
        boards = list(boards)
        values = [None] * len(boards)
        active, indices = [], []
        for i, board in enumerate(boards):
            if board.is_checkmate():
                values[i] = -MATE_CP if board.turn == chess.WHITE else MATE_CP
            elif board.is_game_over(claim_draw=True):
                values[i] = 0
            else:
                active.append(board_tensor(board))
                indices.append(i)
        if active:
            # SavedModel with fixed batch=1 cannot accept multiple boards at once.
            # Execute compatible microbatches while keeping the public batch API.
            chunks = [[a] for a in active] if self.fixed_batch_one else [active]
            try:
                predictions = []
                for chunk in chunks:
                    x = self.tf.convert_to_tensor(np.stack(chunk, axis=0), dtype=self.dtype)
                    result = self.fn(**{self.input_name: x}) if self.input_name is not None else self.fn(x)
                    if isinstance(result, dict):
                        if len(result) != 1:
                            raise EvaluatorError(f'SavedModel debe entregar una salida, recibio {list(result)}')
                        result = next(iter(result.values()))
                    result = np.asarray(result)
                    if result.size != len(chunk):
                        raise EvaluatorError(f'SavedModel devolvio {result.size} valores para {len(chunk)} tableros')
                    predictions.extend(result.reshape(-1))
                for i, v in zip(indices, predictions):
                    cp = normalized_to_cp(v)
                    values[i] = cp if boards[i].turn == chess.WHITE else -cp
            except EvaluatorError:
                raise
            except Exception as exc:
                raise EvaluatorError(f'fallo inferencia TensorFlow por lotes: {exc}') from exc
        return values

    def evaluate(self, board: chess.Board) -> int:
        return self.evaluate_batch([board])[0]
