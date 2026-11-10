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
#* Implementa el jugador base
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
from abc import ABC, abstractmethod
import chess
from ..types import MoveChoice

class PlayerError(RuntimeError):
    pass

class Player(ABC):
    name = "BASE"
    @abstractmethod
    def choose(self, board: chess.Board) -> MoveChoice:
        raise NotImplementedError
    def close(self) -> None:
        return None
