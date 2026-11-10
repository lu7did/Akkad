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
#* random_player.py
#* Implementa el jugador random player
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
import random, time
import chess
from .base import Player
from ..types import MoveChoice

class RandomPlayer(Player):
    name = "RANDOM"
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
    def choose(self, board: chess.Board) -> MoveChoice:
        t0 = time.monotonic()
        moves = list(board.legal_moves)
        move = self.rng.choice(moves) if moves else None
        return MoveChoice(move, 0, 0, len(moves), (time.monotonic()-t0)*1000, self.name)
