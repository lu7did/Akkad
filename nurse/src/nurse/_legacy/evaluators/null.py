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
#* null.py
#* Implementa el evaluador null
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import chess

from .base import Evaluator, EvaluatorError


class NullEvaluator(Evaluator):
    """Sentinel evaluator for monolithic players with internal evaluation.

    NULL deliberately has no evaluation capability.  It exists so the engine
    configuration can state explicitly that a monolithic player (currently
    Stockfish) owns both search and evaluation internally.
    """

    name = "NULL"
    trainable = False

    def evaluate(self, board: chess.Board) -> int:
        raise EvaluatorError(
            "evaluator=NULL no puede evaluar posiciones; sólo es válido con player=stockfish"
        )
