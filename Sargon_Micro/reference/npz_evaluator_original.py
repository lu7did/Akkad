from __future__ import annotations
import os
import numpy as np
import chess
from .base import Evaluator, EvaluatorError

PIECE_FEATURES = 64 * 12
STATE_FEATURES = 4 + 8 + 1
INPUT_SIZE = PIECE_FEATURES + STATE_FEATURES
HIDDEN_SIZE = 64
CALIBRATION_FACTOR = 400.0

class NpzEvaluator(Evaluator):
    """Sargon-NPZ 781-64-1; legacy 32-neuron checkpoints are incompatible."""
    name = "SARGON-NPZ"
    trainable = True

    def __init__(self, path: str, require_weights: bool = True):
        self.path = path
        self._init_random()
        if os.path.exists(path):
            self._load(path)
        elif require_weights:
            raise EvaluatorError(f"NNUE .npz inexistente: {path}")

    def _init_random(self) -> None:
        rng = np.random.default_rng(42)
        self.w_ih = rng.normal(0.0, 0.01, (INPUT_SIZE, HIDDEN_SIZE))
        self.b_h = np.zeros(HIDDEN_SIZE)
        self.w_ho = rng.normal(0.0, 0.1, (HIDDEN_SIZE, 1))
        self.b_o = 0.0
        self.hm_w = float(rng.normal(0.0, 0.005))

    def _load(self, path: str) -> None:
        with np.load(path, allow_pickle=False) as data:
            required = {"w_ih", "b_h", "w_ho", "b_o", "hm_w"}
            missing = required.difference(data.files)
            if missing:
                raise EvaluatorError(f"checkpoint NPZ incompleto: {sorted(missing)}")
            w_ih = np.asarray(data["w_ih"], dtype=float)
            b_h = np.asarray(data["b_h"], dtype=float)
            w_ho = np.asarray(data["w_ho"], dtype=float)
            if w_ih.shape != (INPUT_SIZE, HIDDEN_SIZE) or b_h.shape != (HIDDEN_SIZE,) or w_ho.shape != (HIDDEN_SIZE, 1):
                raise EvaluatorError("checkpoint NPZ incompatible: se requiere 781-64-1 (modelos antiguos 781-32-1 no cargan)")
            self.w_ih, self.b_h, self.w_ho = w_ih, b_h, w_ho
            self.b_o = float(np.asarray(data["b_o"]).item())
            self.hm_w = float(np.asarray(data["hm_w"]).item())

    def reload(self) -> None:
        self._load(self.path)

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        np.savez(self.path, w_ih=self.w_ih, b_h=self.b_h, w_ho=self.w_ho,
                 b_o=np.asarray(self.b_o), hm_w=np.asarray(self.hm_w))

    @staticmethod
    def _piece_feature(square: int, piece_type: int, color: bool) -> int:
        return square * 12 + (piece_type - 1) + (0 if color == chess.WHITE else 6)

    def active_features(self, board: chess.Board) -> list[int]:
        out = [self._piece_feature(sq, p.piece_type, p.color) for sq, p in board.piece_map().items()]
        offset = PIECE_FEATURES
        if board.has_kingside_castling_rights(chess.WHITE): out.append(offset + 0)
        if board.has_queenside_castling_rights(chess.WHITE): out.append(offset + 1)
        if board.has_kingside_castling_rights(chess.BLACK): out.append(offset + 2)
        if board.has_queenside_castling_rights(chess.BLACK): out.append(offset + 3)
        offset += 4
        if board.ep_square is not None and board.has_legal_en_passant():
            out.append(offset + chess.square_file(board.ep_square))
        offset += 8
        if board.turn == chess.WHITE: out.append(offset)
        return out

    def forward_raw(self, board: chess.Board) -> tuple[np.ndarray, np.ndarray, float]:
        features = self.active_features(board)
        acc = np.sum(self.w_ih[features], axis=0) + self.b_h if features else self.b_h.copy()
        hidden = np.maximum(0.0, acc)
        raw = float((hidden @ self.w_ho).item() + self.b_o + (board.halfmove_clock / 50.0) * self.hm_w)
        return acc, hidden, raw

    def evaluate(self, board: chess.Board) -> int:
        return int(self.forward_raw(board)[2] * CALIBRATION_FACTOR)
