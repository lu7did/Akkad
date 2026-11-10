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
#* classic.py
#* Implementa el evaluador classic
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import chess

from .base import Evaluator
from ..types import MATE_CP

# Canonical CLASSIC evaluator ported from Challenger v0.1.0 SargonEngine.
# Contract: centipawns from White's perspective.
PIECE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXT_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.F4, chess.C5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


class ClassicEvaluator(Evaluator):
    """Challenger Sargon static evaluator, exposed through the common contract.

    The original Challenger code evaluates from an arbitrary root colour in pawn
    units and later applies tanh(score / 8).  Here we expose the same underlying
    heuristic from White's perspective in centipawns.  The transform is strictly
    monotonic, so SARGON's move ordering is preserved while the evaluator remains
    interchangeable with NNUE evaluators that also return centipawns.
    """

    name = "CLASSIC"

    def _material(self, board: chess.Board) -> int:
        score = 0
        for piece in board.piece_map().values():
            score += PIECE[piece.piece_type] * (1 if piece.color == chess.WHITE else -1)
        return score

    def _activity(self, board: chess.Board) -> int:
        score = 0.0
        for sq, piece in board.piece_map().items():
            sign = 1.0 if piece.color == chess.WHITE else -1.0
            score += sign * 1.5 * len(board.attacks(sq))
            if sq in CENTER:
                score += sign * (10.0 if piece.piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP) else 4.0)
            elif sq in EXT_CENTER:
                score += sign * 2.5
            if piece.piece_type == chess.KNIGHT:
                starts = (chess.B1, chess.G1) if piece.color == chess.WHITE else (chess.B8, chess.G8)
                if sq in starts:
                    score -= sign * 8.0
            elif piece.piece_type == chess.BISHOP:
                starts = (chess.C1, chess.F1) if piece.color == chess.WHITE else (chess.C8, chess.F8)
                if sq in starts:
                    score -= sign * 6.0
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += 12.0
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= 12.0
        return int(round(score))

    def _pawn_structure(self, board: chess.Board) -> int:
        score = 0.0
        for color, sign in ((chess.WHITE, 1.0), (chess.BLACK, -1.0)):
            pawns = list(board.pieces(chess.PAWN, color))
            files = [chess.square_file(sq) for sq in pawns]
            counts = {f: files.count(f) for f in set(files)}
            score -= sign * 8.0 * sum(max(0, n - 1) for n in counts.values())
            occupied = set(files)
            isolated = sum(1 for f in occupied if f - 1 not in occupied and f + 1 not in occupied)
            score -= sign * 4.0 * isolated
        return int(round(score))

    def _king_safety(self, board: chess.Board) -> int:
        score = 0.0
        for color, sign in ((chess.WHITE, 1.0), (chess.BLACK, -1.0)):
            king = board.king(color)
            if king is None:
                continue
            if board.turn == color and board.is_check():
                score -= sign * 35.0
            kf, kr = chess.square_file(king), chess.square_rank(king)
            direction = 1 if color == chess.WHITE else -1
            rr = kr + direction
            shield = 0
            if 0 <= rr < 8:
                for ff in (kf - 1, kf, kf + 1):
                    if 0 <= ff < 8:
                        p = board.piece_at(chess.square(ff, rr))
                        if p and p.color == color and p.piece_type == chess.PAWN:
                            shield += 1
            score += sign * 5.0 * shield
            ring = chess.SquareSet(chess.BB_KING_ATTACKS[king])
            danger = sum(1 for sq in ring if board.is_attacked_by(not color, sq))
            score -= sign * 3.5 * danger
        return int(round(score))

    def evaluate(self, board: chess.Board) -> int:
        if board.is_checkmate():
            return -MATE_CP if board.turn == chess.WHITE else MATE_CP
        if board.is_game_over(claim_draw=True):
            return 0
        return self._material(board) + self._activity(board) + self._pawn_structure(board) + self._king_safety(board)
