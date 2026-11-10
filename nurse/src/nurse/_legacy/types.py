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
#* types.py
#* Implementa funciones del modulo types
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
from dataclasses import dataclass
import chess

MATE_CP = 100_000

@dataclass(slots=True)
class MoveChoice:
    move: chess.Move | None
    score_cp: int
    depth: int
    nodes: int = 0
    elapsed_ms: float = 0.0
    source: str = ""
