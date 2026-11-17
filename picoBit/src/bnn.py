"""picoBit BNN inference v0.1.1; Keras compatibility with terasPlay.py.

Contract: chess.Board -> integer centipawns from White's perspective.
The model's sigmoid output is interpreted as a White-win-like probability,
exactly as in the supplied reference. No side-to-move sign inversion.
"""
from __future__ import annotations

import math
from pathlib import Path
import chess
import numpy as np

VERSION = '0.1.1'
MATE_CP = 10000
INPUT_SHAPE = (8, 8, 13)
PIECE_INDEX = {(piece_type, color): piece_type - 1 + (0 if color == chess.WHITE else 6)
               for color in (chess.WHITE, chess.BLACK) for piece_type in range(1, 7)}


def board_tensor(board: chess.Board) -> np.ndarray:
    """Reproduce terasPlay: indices a1=(row 0,col 0), h8=(row 7,col 7).

    0..5 white P,N,B,R,Q,K; 6..11 black; 12 side-to-move (+1 W, -1 B).
    Do not mirror black-to-move positions.
    """
    result = np.zeros((1, *INPUT_SHAPE), dtype=np.float32)
    for square, piece in board.piece_map().items():
        row, col = divmod(square, 8)
        result[0, row, col, PIECE_INDEX[(piece.piece_type, piece.color)]] = 1.0
    result[0, :, :, 12] = 1.0 if board.turn == chess.WHITE else -1.0
    return result


def probability_to_white_cp(value: float) -> int:
    """The original calibration: -400*log10(1/p-1), clipped at 1e-4/1-1e-4.

    Round to integer centipawns to match Nurse's evaluation contract.
    """
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('BNN: probabilidad de salida no finita')
    if value < 0.0 or value > 1.0:
        raise ValueError(f'BNN: salida {value} fuera del intervalo [0,1]; se requiere cabeza sigmoid')
    value = min(max(value, .0001), .9999)
    return int(round(400.0 * math.log10(value / (1.0 - value))))


def _custom_layers(tf):
    """Define the two custom classes needed to deserialize terasPlay .keras.

    Delayed TensorFlow import avoids loading TF just to enumerate evaluators.
    In the provided terasPlay.py, axis=, is invalid Python; for convolution
    alpha must be computed over (kernel_h, kernel_w, in_channels) per filter.
    """
    class BinaryConv2D(tf.keras.layers.Layer):
        def __init__(self, filters, kernel_size, binarize_input=True, **kwargs):
            super().__init__(**kwargs)
            self.filters = int(filters)
            self.kernel_size = int(kernel_size)
            self.binarize_input = bool(binarize_input)

        def build(self, input_shape):
            self.w = self.add_weight(
                shape=(self.kernel_size, self.kernel_size, int(input_shape[-1]), self.filters),
                initializer='he_normal', trainable=True,
            )
            super().build(input_shape)

        def call(self, inputs):
            alpha = tf.reduce_mean(tf.abs(self.w), axis=(0, 1, 2), keepdims=True)
            w_bin = tf.where(self.w >= 0, 1.0, -1.0) * alpha
            w_ste = self.w + tf.stop_gradient(w_bin - self.w)
            if self.binarize_input:
                x_clip = tf.clip_by_value(inputs, -1.0, 1.0)
                x_bin = tf.where(x_clip >= 0, 1.0, -1.0)
                inputs = x_clip + tf.stop_gradient(x_bin - x_clip)
            return tf.nn.conv2d(inputs, w_ste, strides=1, padding='SAME')

        def get_config(self):
            return dict(super().get_config(), filters=self.filters,
                        kernel_size=self.kernel_size, binarize_input=self.binarize_input)

    class BinaryDense(tf.keras.layers.Layer):
        def __init__(self, units, **kwargs):
            super().__init__(**kwargs)
            self.units = int(units)

        def build(self, input_shape):
            self.w = self.add_weight(shape=(int(input_shape[-1]), self.units),
                                     initializer='he_normal', trainable=True)
            super().build(input_shape)

        def call(self, inputs):
            alpha = tf.reduce_mean(tf.abs(self.w), axis=0, keepdims=True)
            w_bin = tf.where(self.w >= 0, 1.0, -1.0) * alpha
            w_ste = self.w + tf.stop_gradient(w_bin - self.w)
            clipped = tf.clip_by_value(inputs, -1.0, 1.0)
            x_bin = tf.where(clipped >= 0, 1.0, -1.0)
            x_ste = clipped + tf.stop_gradient(x_bin - clipped)
            return tf.matmul(x_ste, w_ste)

        def get_config(self):
            return dict(super().get_config(), units=self.units)

    return {'BinaryConv2D': BinaryConv2D, 'BinaryDense': BinaryDense}


class BNNEvaluator:
    name = 'BNN'
    trainable = False

    def __init__(self, network: str):
        if not network:
            raise ValueError('BNN requiere ruta de pesos en evaluator.network')
        model_path = Path(network).expanduser().resolve()
        if model_path.suffix.lower() != '.keras' or not model_path.is_file():
            raise FileNotFoundError(f'BNN requiere un archivo .keras válido: {model_path}')
        try:
            import tensorflow as tf
        except ImportError as exc:
            raise RuntimeError('BNN necesita TensorFlow; instalar tensorflow compatible con Python') from exc
        self.tf = tf
        try:
            self.model = tf.keras.models.load_model(
                str(model_path), custom_objects=_custom_layers(tf), compile=False, safe_mode=True)
        except Exception as exc:
            raise RuntimeError(f'BNN no pudo cargar modelo .keras {model_path}: {exc}') from exc
        # Reject incompatible tensor layouts rather than silently permuting features.
        try:
            inp = self.model.input_shape
            if isinstance(inp, list):
                if len(inp) != 1: raise ValueError('múltiples entradas')
                inp = inp[0]
            if len(inp) != 4 or tuple(inp[1:]) != INPUT_SHAPE or inp[0] not in (1, None):
                raise ValueError(f'entrada incompatible {inp}; se requiere (None,8,8,13)')
            out = self.model.output_shape
            if isinstance(out, list):
                if len(out) != 1: raise ValueError('múltiples salidas')
                out = out[0]
            if out not in ((None, 1), (1, 1), (None,), (1,)):
                raise ValueError(f'salida incompatible {out}; se requiere una probabilidad escalar')
        except (TypeError, AttributeError) as exc:
            raise ValueError('BNN modelo sin formas de entrada/salida verificables') from exc
        self._infer = tf.function(lambda x: self.model(x, training=False), reduce_retracing=True)
        self.source = str(model_path)
        self.nodos_evaluados = 0

    def evaluate(self, board: chess.Board) -> int:
        self.nodos_evaluados += 1
        if board.is_checkmate():
            return -MATE_CP if board.turn == chess.WHITE else MATE_CP
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0
        prediction = np.asarray(self._infer(self.tf.convert_to_tensor(board_tensor(board))))
        if prediction.size != 1:
            raise ValueError(f'BNN requiere una salida escalar, obtuvo {prediction.shape}')
        return probability_to_white_cp(float(prediction.reshape(-1)[0]))

    def evaluate_with_hint(self, board, *, incremental=False, previous_state=None):
        return self.evaluate(board), None

    def close(self):
        self.model = None
        self._infer = None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='picoBit BNN test: scores are White-POV centipawns')
    parser.add_argument('--network')
    parser.add_argument('--fen', default=chess.STARTING_FEN)
    parser.add_argument('--version', action='version', version=VERSION)
    args = parser.parse_args()
    if not args.network: parser.error('--network requerido')
    evaluator = BNNEvaluator(args.network)
    print(f'BNN score_cp_white={evaluator.evaluate(chess.Board(args.fen))} source={evaluator.source}')
