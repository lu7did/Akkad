#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* cerebrum_v11.py
#* Implementa el evaluador cerebrum v11
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
import chess

from .base import Evaluator, EvaluatorError

L0 = 768
A = 128
B = 32
OUT = 2
Q_STANDARD = 127.0 / 64.0
Q_QUANT = 64
REQUIRED = A * L0 + A + B * (2 * A) + B + OUT * B + OUT
_INT_RE = re.compile(r"^[+-]?\d+$")


@dataclass(slots=True)
class CerebrumV11Evaluation:
    """Detailed Cerebrum 1.1 inference result.

    `score_cp` is the public Sargon-NNUE score (White perspective).
    `score_white_float_cp` preserves the pre-integer precision for tie-breaking.
    The two accumulators are absolute White/Black-perspective first-layer
    accumulators, so they remain reusable when side-to-move changes.
    `piece_map` is the position snapshot used to update the accumulators by
    delta after a move.
    """

    score_cp: int
    score_white_float_cp: float
    raw_side_to_move: float
    wr: float
    mt: float
    acc_white: np.ndarray
    acc_black: np.ndarray
    l1: np.ndarray
    l2: np.ndarray
    l3: np.ndarray
    piece_map: dict[int, chess.Piece]


class CerebrumV11Evaluator(Evaluator):
    """Evaluator for the default Cerebrum 1.1 network.

    Exact supported architecture: 2x(768->128)->32->2.
    Accepts both upstream text formats:
      * epoch-XX.txt   : standard/full precision
      * epoch-XX-q.txt : quantized int8-style export

    Besides the stable `evaluate(board) -> int` contract, this evaluator exposes
    `evaluate_detailed()` and `evaluate_incremental()` so a player may reuse the
    NNUE first-layer accumulators without depending on Cerebrum internals.
    """

    name = "CEREBRUM-1.1"
    trainable = False

    def __init__(self, path: str, a: int | None = None, b: int | None = None):
        if a not in (None, A) or b not in (None, B):
            raise EvaluatorError(
                "CEREBRUM-1.1 soporta exactamente el default 2x(768->128)->32->2"
            )
        self.path = path
        self.metadata: dict[str, object] = {}
        self.quantized = False
        self._load()

    def reload(self) -> None:
        self._load()

    def _load(self) -> None:
        p = Path(self.path)
        if not p.is_file():
            raise EvaluatorError(f"red Cerebrum 1.1 inexistente: {p}")
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise EvaluatorError(
                "CEREBRUM-1.1 espera epoch-XX.txt o epoch-XX-q.txt textual; no un .nn binario"
            ) from exc
        self._load_text(text)

    def _load_text(self, text: str) -> None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 5:
            raise EvaluatorError("cabecera Cerebrum 1.1 incompleta")
        expected_keys = ("name=", "author=", "parameters=", "wr=", "mt=")
        if any(not lines[i].startswith(key) for i, key in enumerate(expected_keys)):
            raise EvaluatorError(
                "cabecera Cerebrum 1.1 inválida; se esperan name, author, parameters, wr y mt"
            )

        try:
            expected = int(lines[2].split("=", 1)[1])
            self.wr_factor = float(lines[3].split("=", 1)[1])
            self.mt_factor = float(lines[4].split("=", 1)[1])
        except ValueError as exc:
            raise EvaluatorError("metadatos numéricos Cerebrum 1.1 inválidos") from exc

        raw_values = lines[5:]
        if expected != REQUIRED:
            raise EvaluatorError(
                f"arquitectura Cerebrum 1.1 incompatible: declara {expected} parámetros; "
                f"el default 2x(768->128)->32->2 requiere {REQUIRED}"
            )
        if len(raw_values) != expected:
            raise EvaluatorError(
                f"Cerebrum 1.1 declara {expected} parámetros pero contiene {len(raw_values)}"
            )

        self.quantized = all(_INT_RE.match(v) is not None for v in raw_values)
        try:
            values = np.asarray(
                [int(v) for v in raw_values] if self.quantized else [float(v) for v in raw_values],
                dtype=np.int64 if self.quantized else np.float64,
            )
        except ValueError as exc:
            raise EvaluatorError("peso Cerebrum 1.1 no numérico") from exc

        self.metadata = {
            "name": lines[0][5:],
            "author": lines[1][7:],
            "parameters": expected,
            "wr_factor": self.wr_factor,
            "mt_factor": self.mt_factor,
            "format": "quantized" if self.quantized else "standard",
        }

        i = 0
        # Upstream export is [output row][input col]; the official Python
        # inference transposes every weight matrix after loading.
        w0 = values[i : i + A * L0].reshape(A, L0)
        i += A * L0
        self.W0 = w0.T.copy()  # [768,128]
        self.B0 = values[i : i + A].copy()
        i += A

        w1 = values[i : i + B * (2 * A)].reshape(B, 2 * A)
        i += B * (2 * A)
        self.W1 = w1.T.copy()  # [256,32]
        self.B1 = values[i : i + B].copy()
        i += B

        w2 = values[i : i + OUT * B].reshape(OUT, B)
        i += OUT * B
        self.W2 = w2.T.copy()  # [32,2]
        self.B2 = values[i : i + OUT].copy()

    @staticmethod
    def _feature_index(piece: chess.Piece, square: int, perspective: chess.Color) -> int:
        """Cerebrum HalfKP-like 12x64 feature for one absolute perspective."""
        piece_index = piece.piece_type - 1
        if perspective == chess.WHITE:
            channel_color = 0 if piece.color == chess.WHITE else 1
            oriented_square = square
        else:
            channel_color = 0 if piece.color == chess.BLACK else 1
            oriented_square = square ^ 56
        return 64 * (2 * piece_index + channel_color) + oriented_square

    def _build_accumulators(self, board: chess.Board) -> tuple[np.ndarray, np.ndarray]:
        acc_white = self.B0.copy()
        acc_black = self.B0.copy()
        for square, piece in board.piece_map().items():
            acc_white += self.W0[self._feature_index(piece, square, chess.WHITE)]
            acc_black += self.W0[self._feature_index(piece, square, chess.BLACK)]
        return acc_white, acc_black

    def _forward_from_accumulators(
        self,
        board: chess.Board,
        acc_white: np.ndarray,
        acc_black: np.ndarray,
        *,
        piece_map: dict[int, chess.Piece] | None = None,
    ) -> CerebrumV11Evaluation:
        # Cerebrum concatenates side-to-move perspective first.
        if board.turn == chess.WHITE:
            acc_stm, acc_opp = acc_white, acc_black
        else:
            acc_stm, acc_opp = acc_black, acc_white

        l1 = np.concatenate((acc_stm, acc_opp), axis=0)
        if self.quantized:
            l1 = np.clip(l1, 0, 127)
            l2 = l1 @ self.W1 + (self.B1 * Q_QUANT)
            l2 = l2 // Q_QUANT
            l2 = np.clip(l2, 0, 127)
            l3 = l2 @ self.W2 + (self.B2 * Q_QUANT)
            l3 = l3 // Q_QUANT
            l3 = l3.astype(float) / Q_QUANT
        else:
            l1 = np.clip(l1, 0.0, Q_STANDARD)
            l2 = l1 @ self.W1 + self.B1
            l2 = np.clip(l2, 0.0, Q_STANDARD)
            l3 = l2 @ self.W2 + self.B2

        wr = float(l3[0])
        mt = float(l3[1])
        raw = wr * self.wr_factor + mt * self.mt_factor
        stm_float_cp = 1000.0 * raw
        white_float_cp = stm_float_cp if board.turn == chess.WHITE else -stm_float_cp
        # Preserve the upstream integer semantics first, then flip perspective.
        stm_score = int(stm_float_cp)
        score_cp = stm_score if board.turn == chess.WHITE else -stm_score

        return CerebrumV11Evaluation(
            score_cp=score_cp,
            score_white_float_cp=white_float_cp,
            raw_side_to_move=raw,
            wr=wr,
            mt=mt,
            acc_white=acc_white.copy(),
            acc_black=acc_black.copy(),
            l1=np.asarray(l1).copy(),
            l2=np.asarray(l2).copy(),
            l3=np.asarray(l3).copy(),
            piece_map=dict(board.piece_map()) if piece_map is None else dict(piece_map),
        )

    def evaluate_detailed(self, board: chess.Board) -> CerebrumV11Evaluation:
        """Full evaluation including reusable first-layer accumulators."""
        acc_white, acc_black = self._build_accumulators(board)
        return self._forward_from_accumulators(board, acc_white, acc_black)

    def evaluate_incremental(
        self,
        board: chess.Board,
        parent: CerebrumV11Evaluation,
    ) -> CerebrumV11Evaluation:
        """Evaluate a child position by applying piece deltas to parent accumulators.

        This mirrors the purpose of Cerebrum's native C accumulator API while
        remaining robust for captures, en-passant, promotions, castling and
        Chess960: the delta is derived from the two piece maps rather than from
        special-case move logic.
        """
        acc_white = parent.acc_white.copy()
        acc_black = parent.acc_black.copy()
        old_map = parent.piece_map
        new_map = board.piece_map()

        changed = set(old_map) | set(new_map)
        for square in changed:
            old_piece = old_map.get(square)
            new_piece = new_map.get(square)
            if old_piece == new_piece:
                continue
            if old_piece is not None:
                acc_white -= self.W0[self._feature_index(old_piece, square, chess.WHITE)]
                acc_black -= self.W0[self._feature_index(old_piece, square, chess.BLACK)]
            if new_piece is not None:
                acc_white += self.W0[self._feature_index(new_piece, square, chess.WHITE)]
                acc_black += self.W0[self._feature_index(new_piece, square, chess.BLACK)]

        return self._forward_from_accumulators(
            board, acc_white, acc_black, piece_map=dict(new_map)
        )

    def evaluate(self, board: chess.Board) -> int:
        # Stable generic contract: White-perspective integer centipawns.
        return self.evaluate_detailed(board).score_cp


    def evaluate_with_hint(self, board: chess.Board, *, incremental: bool = False, previous_state=None) -> tuple[int, object | None]:
        """Cerebrum 1.1 opts in to the generic optional incremental contract."""
        if not incremental:
            return self.evaluate(board), None
        if isinstance(previous_state, CerebrumV11Evaluation):
            current = self.evaluate_incremental(board, previous_state)
        else:
            current = self.evaluate_detailed(board)
        return int(current.score_cp), current
