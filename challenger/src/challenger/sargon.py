from __future__ import annotations

"""SARGON 1978-inspired fixed-depth engine.

Algorithmic approximation, NOT a verified translation of the 1978 Z80
exchange evaluator or complete move-generation/evaluation rules.

The search uses fixed ply, full legal move generation, alpha-beta bounds,
no quiescence, no heuristic move sorting, no transposition table and no random
root tie-breaking.  python-chess handles rules and board representation.
"""

import time
from dataclasses import dataclass
import chess

# Relative material units are an approximation, not claimed to be the
# historical Spracklen constants.
PIECE = {chess.PAWN: 1.0, chess.KNIGHT: 3.0, chess.BISHOP: 3.0,
         chess.ROOK: 5.0, chess.QUEEN: 9.0, chess.KING: 0.0}
MATE = 10000.0


@dataclass(slots=True)
class SearchResult:
    move: chess.Move
    score: float
    nodes: int
    elapsed: float


class SearchTimeout(TimeoutError):
    """Assigned move time has expired."""


class SargonEngine:
    """Fixed-depth nonselective SARGON-style algorithmic reference.

    qdepth is accepted ONLY as zero to make departures explicit. The original
    historical XCHNG evaluator is not reproduced byte-for-byte here.
    """

    def __init__(self, plies: int = 2, qdepth: int = 0, seed: int | None = None):
        if plies < 1:
            raise ValueError("plies debe ser >= 1")
        if qdepth != 0:
            raise ValueError("Sargon histórico no utiliza qdepth; use --qdepth 0")
        self.plies = int(plies)
        self.qdepth = 0
        self.nodes = 0
        self._deadline: float | None = None
        # seed retained in signature for compatibility; historic reference
        # breaks equal-scoring moves deterministically.

    def _check_deadline(self):
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise SearchTimeout("Sargon agotó su tiempo de juego")

    def _least_valuable_legal_capture(self, board: chess.Board, target: int):
        """Least valuable legal capturer of target, recomputed after each exchange.

        Uses legal moves (pins, king safety and discovered sliding attackers are
        respected) while remaining confined to one contested square.
        """
        candidates = []
        for src in board.attackers(board.turn, target):
            piece = board.piece_at(src)
            if piece is None:
                continue
            # Historical attack lists are ordered by piece value. Ties use
            # square index so that evaluation is deterministic.
            move = chess.Move(src, target)
            if piece.piece_type == chess.PAWN and chess.square_rank(target) in (0, 7):
                move = chess.Move(src, target, promotion=chess.QUEEN)
            if board.is_legal(move) and board.is_capture(move):
                candidates.append((PIECE[piece.piece_type], src, move))
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[0], item[1]))[2]

    def _exchange_gain(self, board: chess.Board, target: int, remaining: int) -> float:
        """Static exchange sequence for one square; the mover may stop.

        This is a modern legal-move implementation of the attack/defend and
        least-valuable-attacker idea behind SARGON XCHNG/NEXTAD, rather than
        a literal reproduction of their register arithmetic or POINTS.
        """
        if remaining <= 0:
            return 0.0
        move = self._least_valuable_legal_capture(board, target)
        if move is None:
            return 0.0
        victim = board.piece_at(target)
        if victim is None or victim.piece_type == chess.KING:
            return 0.0
        captured = PIECE[victim.piece_type]
        board.push(move)
        try:
            return max(0.0, captured - self._exchange_gain(board, target, remaining - 1))
        finally:
            board.pop()

    def _exchange_risk(self, board: chess.Board, color: chess.Color) -> float:
        """Material exposed to static capture sequences, from color's view.

        As in historical POINTS, we avoid treating all simultaneous battles
        as independent realizable losses: take the largest adverse residue.
        This is an approximation of the original combination rule.
        """
        adverse = 0.0
        attacker = not color
        for square, piece in board.piece_map().items():
            if piece.color != color or piece.piece_type == chess.KING:
                continue
            if not board.is_attacked_by(attacker, square):
                continue
            simulation = board.copy(stack=False)
            simulation.turn = attacker
            adverse = max(adverse, self._exchange_gain(simulation, square, 16))
        return adverse

    def _evaluate(self, board: chess.Board, root: chess.Color, ply_from_root: int):
        if board.is_checkmate():
            return (-MATE + ply_from_root) if board.turn == root else (MATE - ply_from_root)
        if board.is_game_over(claim_draw=True):
            return 0.0
        material = sum(PIECE[p.piece_type] * (1 if p.color == root else -1)
                       for p in board.piece_map().values())
        return material - self._exchange_risk(board, root) + self._exchange_risk(board, not root)

    def _minimax(self, board: chess.Board, depth: int, alpha: float,
                 beta: float, root: chess.Color, ply_from_root: int) -> float:
        self._check_deadline()
        self.nodes += 1
        if depth == 0 or board.is_game_over(claim_draw=True):
            return self._evaluate(board, root, ply_from_root)
        # Keep native python-chess legal order. No MVV-LVA, checks-first,
        # killer/history, TT, quiescence, extensions or reductions.
        if board.turn == root:
            best = -float("inf")
            for move in board.legal_moves:
                board.push(move)
                try:
                    value = self._minimax(board, depth - 1, alpha, beta,
                                          root, ply_from_root + 1)
                finally:
                    board.pop()
                best = max(best, value)
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
            return best
        best = float("inf")
        for move in board.legal_moves:
            board.push(move)
            try:
                value = self._minimax(board, depth - 1, alpha, beta,
                                      root, ply_from_root + 1)
            finally:
                board.pop()
            best = min(best, value)
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best

    def choose(self, board: chess.Board, deadline: float | None = None) -> SearchResult:
        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No hay movimientos legales")
        start = time.monotonic()
        self.nodes = 0
        self._deadline = deadline
        root = board.turn
        best_move = None
        best_score = -float("inf")
        try:
            for move in legal:
                self._check_deadline()
                board.push(move)
                try:
                    score = self._minimax(board, self.plies - 1,
                                          -float("inf"), float("inf"), root, 1)
                finally:
                    board.pop()
                # Original-equivalent tie order has not been established.
                # Deterministic first maximum, with no artificial randomness.
                if score > best_score:
                    best_score, best_move = score, move
            return SearchResult(move=best_move, score=best_score,
                                nodes=self.nodes, elapsed=time.monotonic() - start)
        finally:
            self._deadline = None
