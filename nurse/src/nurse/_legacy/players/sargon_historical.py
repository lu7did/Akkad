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
#* sargon_historical.py
#* Algoritmo de búsqueda SARGON: aproximación histórica, no emulación Z80.
#* v0.6.153
#=================================================================================================================*
"""Algoritmo de búsqueda SARGON: aproximación histórica, no emulación Z80.

Sólo la fábrica player=sargon crea esta clase.  No modifica SargonCore ni
SargonPlusPlayer, por lo que BOOST/TURBO y la quiescence moderna permanecen
idénticos a los de la distribución de partida.

Diferencias deliberadas respecto del SARGON ensamblador: se usa python-chess
para generar jugadas y un Evaluator inyectado (CLASSIC/NPZ/CEREBRUM/STOCKFISH)
para asignar valores, no la transcripción exacta de POINTS/XCHNG.
"""
from __future__ import annotations

import time
import sys
import chess

from .sargon import SargonCore
from ..types import MoveChoice, MATE_CP


class SargonHistoricalPlayer(SargonCore):
    name = "SARGON"

    def __init__(self, evaluator, depth: int = 2, qdepth: int = 0,
                 tmax_ms: int | None = None, seed: int | None = None,
                 iterative_deepening: bool = False, telemetry=None, audit=None):
        # qdepth/iterative_deepening are accepted as compatibility inputs only.
        if qdepth is not None and int(qdepth) != 0:
            warning = f"❌ qdepth={qdepth} inválido con player=sargon, ignored"
            # Never write diagnostics into the UCI protocol channel (stdout).
            # Windows CP1252 stderr cannot encode the warning emoji.
            try:
                print(warning, file=sys.stderr, flush=True)
            except UnicodeEncodeError:
                print(f"ERROR qdepth={qdepth} invalido con player=sargon, ignored",
                      file=sys.stderr, flush=True)
        # The historical player NEVER uses a qsearch/iterative path.
        super().__init__(evaluator, depth=depth, qdepth=0, tmax_ms=tmax_ms,
                         seed=seed, iterative_deepening=False,
                         telemetry=telemetry, audit=audit)
        self.qdepth = 0
        self.iterative_deepening = False

    def _historical_search(self, board: chess.Board, depth: int,
                           alpha: int, beta: int, root: chess.Color) -> int:
        self.nodes += 1
        if board.is_game_over(claim_draw=True) or depth <= 0:
            return self._static(board, root)
        # Preserve natural generator order: no tactical sorting, TT or qsearch.
        if board.turn == root:
            best = -2 * MATE_CP
            for move in board.legal_moves:
                board.push(move)
                try:
                    value = self._historical_search(board, depth - 1, alpha, beta, root)
                finally:
                    board.pop()
                if value > best:
                    best = value
                if best > alpha:
                    alpha = best
                if alpha >= beta:
                    break
        else:
            best = 2 * MATE_CP
            for move in board.legal_moves:
                board.push(move)
                try:
                    value = self._historical_search(board, depth - 1, alpha, beta, root)
                finally:
                    board.pop()
                if value < best:
                    best = value
                if best < beta:
                    beta = best
                if alpha >= beta:
                    break
        return int(best)

    def choose(self, board: chess.Board) -> MoveChoice:
        start = time.monotonic()
        self.nodes = 0
        root = board.turn
        legal = list(board.legal_moves)
        if not legal:
            return MoveChoice(None, self._static(board, root), self.depth, 0,
                              (time.monotonic()-start)*1000, self.name)
        best_move = None
        best_score = -2 * MATE_CP
        # Full-width *root*; independent windows avoid incomparability of
        # fail-soft child bounds in root-move tie handling.
        for move in legal:
            board.push(move)
            try:
                value = self._historical_search(board, self.depth - 1,
                                                -2 * MATE_CP, 2 * MATE_CP, root)
            finally:
                board.pop()
            if best_move is None or value > best_score:
                best_score = value
                best_move = move
        score_white = best_score if root == chess.WHITE else -best_score
        elapsed_ms = (time.monotonic()-start)*1000
        if self.audit is not None:
            self.audit.event(
                "sargon_historical_result", target_depth=self.depth,
                completed_depth=self.depth, attempted_depth=self.depth,
                timed_out=False, root_total=len(legal), nodes=self.nodes,
                elapsed_ms=elapsed_ms, bestmove=best_move.uci(),
                score_white_cp=int(score_white), qdepth=0,
                search_mode="fixed-depth-alpha-beta", tt=False,
                move_ordering="generator", tmax_enforced=False,
            )
        return MoveChoice(best_move, int(score_white), self.depth,
                          self.nodes, elapsed_ms, self.name)
