"""Microchess (Jennings 1976) inspired strategic evaluator.

The published STRATGY polynomial is reproduced in *quarter pawn* integer
units for candidate moves. GNM/JANUS/STATE and exchanges are reconstructed
at a behavioural level, not instruction-for-instruction from 6502 assembly.
python-chess remains responsible for complete modern move legality.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator
import chess
from .base import Evaluator
from ..types import MATE_CP

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
          chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


class State(IntEnum):
    INITIAL = 0
    CANDIDATE = 4
    CONTINUATION = 5
    RESPONSE = 6
    EXCHANGE_0 = 0xFF
    EXCHANGE_1 = 0xFE
    EXCHANGE_2 = 0xFD
    EXCHANGE_3 = 0xFC
    LEGALITY = 0xF9
    STRATEGY = 7


@dataclass(frozen=True)
class Measurements:
    mob: int = 0
    maxc: int = 0
    cc: int = 0


def gnm(board: chess.Board, color: bool, *, captures_only: bool = False) -> Iterator[chess.Move]:
    """GNM: sequential piece/direction ordered legal moves; never retains a move list.

    Uses the piece-to-square representation (piece_map) and iterates by piece;
    python-chess generates/legalizes moves, including castling and en passant.
    """
    snapshot = board.copy(stack=False)
    snapshot.turn = color
    # For off-turn statistics this is a legal-move approximation: en-passant
    # rights and check conditions belong to the actual board history.
    for source in sorted(snapshot.piece_map()):
        piece = snapshot.piece_at(source)
        if piece is None or piece.color != color:
            continue
        for move in snapshot.generate_pseudo_legal_moves(from_mask=chess.BB_SQUARES[source]):
            if captures_only and not (snapshot.is_capture(move) or move.promotion):
                continue
            # Never include king-exposing moves even when scanning the other side.
            if snapshot.is_legal(move):
                yield move


def measure(board: chess.Board, color: bool) -> Measurements:
    # Historical mobility includes queen moves twice. CC counts distinct
    # threatened pieces, not the same piece for every attacking direction.
    mobility = 0
    threatened = set()
    max_capture = 0
    for move in gnm(board, color):
        piece = board.piece_at(move.from_square)
        if piece and piece.piece_type == chess.QUEEN:
            mobility += 2
        else:
            mobility += 1
        if board.is_en_passant(move):
            victim_value = 1
            victim_square = move.to_square + (-8 if color else 8)
        else:
            victim = board.piece_at(move.to_square)
            victim_value = VALUES[victim.piece_type] if victim and victim.color != color else 0
            victim_square = move.to_square
        if victim_value:
            max_capture = max(max_capture, victim_value)
            threatened.add((victim_square, victim_value))
    return Measurements(mobility, max_capture, sum(v for _, v in threatened))


def capture_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return 1
    piece = board.piece_at(move.to_square)
    return VALUES.get(piece.piece_type, 0) if piece else 0


def exchanges(board: chess.Board, first_color: bool, *, branch: int = 1, plies: int = 6):
    """Selectively explore a best capture sequence; return max capture per turn.

    WCAP0/1/2 and BCAP0/1/2 are taken from alternate plies 0/2/4 and 1/3/5.
    This is a bounded beam approximation to JANUS exchange states, not a
    transcription of historical TREE. Promotion is a legal capture candidate.
    """
    result = [0] * plies
    if board.turn != first_color:
        board = board.copy(stack=False)
        board.turn = first_color
    def walk(level: int, path: tuple[int, ...]):
        if level >= plies:
            return path
        candidates = sorted(
            ((capture_value(board, m), m) for m in gnm(board, board.turn, captures_only=True)
             if board.is_capture(m)),
            key=lambda item: item[0], reverse=True
        )
        if not candidates:
            return path
        best = path
        best_metric = float('-inf')
        for value, move in candidates[:branch]:
            board.push(move)
            try:
                candidate = walk(level + 1, path + (value,))
            finally:
                board.pop()
            # Deterministic alternating exchange utility; first player maximizes.
            metric = sum((1 if i % 2 == 0 else -1) * v for i, v in enumerate(candidate))
            if metric > best_metric:
                best_metric, best = metric, candidate
        return best
    sequence = walk(0, ())
    for i, value in enumerate(sequence[:plies]):
        result[i] = value
    return (result[0], result[2], result[4]), (result[1], result[3], result[5])


def positional_bonus(board: chess.Board, move: chess.Move, color: bool) -> int:
    piece = board.piece_at(move.from_square)
    if piece is None:
        return 0
    rank = chess.square_rank(move.from_square)
    home = 0 if color else 7
    central = move.to_square in (chess.D4, chess.E4, chess.D5, chess.E5)
    develop = piece.piece_type in (chess.KNIGHT, chess.BISHOP) and rank == home
    return 2 if central or develop else 0


def strategy_quarters(p: Measurements, w: Measurements, b: Measurements,
                      wcap: tuple[int,int,int], bcap: tuple[int,int,int]) -> int:
    """4*V with original coefficients; duplicate BMAXC retained as -12.

    Published expression: +16 WCAP0 +5 WCAP1 +3(WMAXC+WCC)
    +(WMOB+WCAP2) -12 BMAXC -8 BCC -5 BCAP1
    -(PMAXC+PCC+PMOB+BCAP0+BCAP2+BMOB).
    """
    return (16*wcap[0] + 5*wcap[1] + 3*(w.maxc+w.cc)
            + w.mob+wcap[2] - 12*b.maxc - 8*b.cc - 5*bcap[1]
            - (p.maxc+p.cc+p.mob+bcap[0]+bcap[2]+b.mob))


class MicrochessEvaluator(Evaluator):
    name = 'MICROCHESS'

    def evaluate(self, board: chess.Board) -> int:
        """Position-only public contract; White-perspective centipawns.

        The historical STRATGY is move-dependent. For other players this
        symmetric position score uses the same mobility/threat vocabulary;
        it does not pretend that missing previous-position data exist.
        """
        if board.is_checkmate():
            return -MATE_CP if board.turn else MATE_CP
        if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves():
            return 0
        white, black = measure(board, chess.WHITE), measure(board, chess.BLACK)
        material = sum((1 if p.color else -1)*VALUES[p.piece_type]
                       for p in board.piece_map().values())
        # Quarter-pawn arithmetic, with material to keep the score meaningful
        # to the other search algorithms independent of candidate history.
        activity = (white.mob-black.mob) + 3*(white.maxc+white.cc-black.maxc-black.cc)
        return int(100*material + 25*activity)

    def evaluate_candidate(self, board: chess.Board, move: chess.Move,
                           *, exchange_branch: int = 1) -> int:
        """Historical-style JANUS pass for Microchess's own move policy.

        Computes candidate-specific measurements before and after the move.
        Returned centipawns are from the side that made *move*; unlike the
        public evaluate(board), this method is deliberately move-relative.
        """
        if move not in board.legal_moves:
            raise ValueError('Candidate move is not legal')
        side = board.turn
        previous = measure(board, side)  # STATE INITIAL
        bonus = positional_bonus(board, move, side)
        immediate = capture_value(board, move)
        board.push(move)
        try:
            # STATE LEGALITY / mate (python-chess supplies full modern rules)
            if board.is_checkmate():
                return MATE_CP
            if board.is_stalemate():
                return 0
            own = measure(board, side)           # STATE CONTINUATION
            rival = measure(board, not side)     # STATE RESPONSE
            # Rival moves first in this position; its captures are BCAP0...
            bc, wc = exchanges(board, not side, branch=exchange_branch)
            wc = (immediate, wc[1], wc[2])
            # STATE STRATEGY: original polynomial in quarter-pawn units.
            quarters = strategy_quarters(previous, own, rival, wc, bc)
            return 25*quarters + 200*bonus
        finally:
            board.pop()
