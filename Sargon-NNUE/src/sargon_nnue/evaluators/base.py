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
#* base.py
#* Implementa el evaluador base
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
from abc import ABC, abstractmethod
import chess

class EvaluatorError(RuntimeError):
    pass

class Evaluator(ABC):
    """Board -> normalized centipawn evaluation from White's perspective."""
    name = "BASE"
    trainable = False

    @abstractmethod
    def evaluate(self, board: chess.Board) -> int:
        raise NotImplementedError

    def reload(self) -> None:
        return None

    def close(self) -> None:
        return None

    def evaluate_with_hint(self, board: chess.Board, *, incremental: bool = False, previous_state=None) -> tuple[int, object | None]:
        """Optional optimization hook. The default ignores the hint.

        Return (White-perspective integer centipawns, reusable opaque state).
        Never require a caller to know the evaluator's implementation.
        """
        return int(self.evaluate(board)), None
