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
#* sargon.py
#* Implementa el jugador sargon
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import random
import time
from dataclasses import dataclass

import chess

from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP

PIECE = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.2,
    chess.BISHOP: 3.3,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
    chess.KING: 0.0,
}


class SearchTimeout(Exception):
    pass


class SargonCore(Player):
    """Canonical SARGON search ported from Challenger v0.1.0.

    Search behaviour intentionally mirrors Challenger: alpha-beta minimax,
    qsearch=2 by default, forcing-move ordering, per-search transposition table,
    deadline checks and random tie-breaking.  The only architectural change is
    that static evaluation is delegated to the common evaluator contract.
    """

    name = "SARGON"

    def __init__(self, evaluator, depth: int = 2, qdepth: int = 2,
                 tmax_ms: int | None = None, seed: int | None = None,
                 iterative_deepening: bool = True, telemetry=None, audit=None):
        if depth < 1:
            raise PlayerError("depth debe ser >= 1")
        if qdepth < 0:
            raise PlayerError("qdepth debe ser >= 0")
        self.evaluator = evaluator
        self.depth = int(depth)
        self.qdepth = int(qdepth)
        self.tmax_ms = tmax_ms
        self.rng = random.Random(seed)
        self.iterative_deepening = True  # v0.6.21: core invariant
        self.telemetry = telemetry
        self.audit = audit
        self.nodes = 0
        self._tt: dict[tuple[str, tuple[str, ...], int, bool], int] = {}
        self._deadline: float | None = None

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise SearchTimeout

    def _root_eval(self, board: chess.Board, root: chess.Color) -> int:
        score_white = int(self.evaluator.evaluate(board))
        return score_white if root == chess.WHITE else -score_white

    def _static(self, board: chess.Board, root: chess.Color) -> int:
        if board.is_checkmate():
            return -MATE_CP if board.turn == root else MATE_CP
        if board.is_game_over(claim_draw=True):
            return 0
        return self._root_eval(board, root)

    def _move_order_score(self, board: chess.Board, move: chess.Move) -> float:
        score = 0.0
        if move.promotion:
            score += 20.0 + PIECE.get(move.promotion, 0.0)
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            vv = PIECE.get(victim.piece_type, 1.0) if victim else 1.0
            av = PIECE.get(attacker.piece_type, 1.0) if attacker else 1.0
            score += 10.0 + vv - 0.1 * av
        if board.gives_check(move):
            score += 6.0
        return score

    def _forcing_moves(self, board: chess.Board) -> list[chess.Move]:
        if board.is_check():
            moves = list(board.legal_moves)
        else:
            moves = [m for m in board.legal_moves
                     if board.is_capture(m) or m.promotion is not None or board.gives_check(m)]
        moves.sort(key=lambda m: self._move_order_score(board, m), reverse=True)
        return moves

    def _quiescence(self, board: chess.Board, depth: int, alpha: int, beta: int,
                    root: chess.Color) -> int:
        self._check_deadline()
        self.nodes += 1
        stand = self._static(board, root)
        if depth <= 0 or board.is_game_over(claim_draw=True):
            return stand
        in_check = board.is_check()
        moves = self._forcing_moves(board)
        if not moves:
            return stand
        if board.turn == root:
            best = -2 * MATE_CP if in_check else stand
            if not in_check and best >= beta:
                return best
            if not in_check:
                alpha = max(alpha, best)
            for move in moves:
                board.push(move)
                try:
                    value = self._quiescence(board, depth - 1, alpha, beta, root)
                finally:
                    board.pop()
                best = max(best, value)
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
            return int(best)
        best = 2 * MATE_CP if in_check else stand
        if not in_check and best <= alpha:
            return best
        if not in_check:
            beta = min(beta, best)
        for move in moves:
            board.push(move)
            try:
                value = self._quiescence(board, depth - 1, alpha, beta, root)
            finally:
                board.pop()
            best = min(best, value)
            beta = min(beta, best)
            if alpha >= beta:
                break
        return int(best)

    def _minimax(self, board: chess.Board, depth: int, alpha: int, beta: int,
                 root: chess.Color) -> int:
        self._check_deadline()
        self.nodes += 1
        if board.is_game_over(claim_draw=True):
            return self._static(board, root)
        if depth <= 0:
            return self._quiescence(board, self.qdepth, alpha, beta, root)
        key = (board.fen(), tuple(move.uci() for move in board.move_stack), depth, root)
        cached = self._tt.get(key)
        if cached is not None:
            return cached
        moves = list(board.legal_moves)
        moves.sort(key=lambda m: self._move_order_score(board, m), reverse=True)
        if board.turn == root:
            best = -2 * MATE_CP
            for move in moves:
                board.push(move)
                try:
                    value = self._minimax(board, depth - 1, alpha, beta, root)
                finally:
                    board.pop()
                best = max(best, value)
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
        else:
            best = 2 * MATE_CP
            for move in moves:
                board.push(move)
                try:
                    value = self._minimax(board, depth - 1, alpha, beta, root)
                finally:
                    board.pop()
                best = min(best, value)
                beta = min(beta, best)
                if alpha >= beta:
                    break
        self._tt[key] = int(best)
        return int(best)

    def _score_root_move(self, board: chess.Board, move: chess.Move, depth: int, root: chess.Color) -> int:
        board.push(move)
        try:
            return MATE_CP if board.is_checkmate() else self._minimax(
                board, max(0, depth - 1), -2 * MATE_CP, 2 * MATE_CP, root
            )
        finally:
            board.pop()

    def _emit_guardrail(self, *, attempted_depth: int, completed_depth: int,
                        root_completed: int, root_total: int, elapsed_ms: float,
                        kind: str = "time") -> None:
        # This is NORMAL telemetry, not audit-only.  The severity reflects
        # whether we still own at least one complete iterative-deepening result.
        # nn/mm means: maximum fully completed depth / requested target depth.
        severity = "⚠️" if completed_depth > 0 else "❌"
        quality = "last-complete-level" if completed_depth > 0 else "imperfect-options-only"
        root_pct = (100.0 * root_completed / root_total) if root_total > 0 else 0.0
        msg = (
            f"{severity} GUARDRAIL {self.name} {kind}: levels={completed_depth}/{self.depth} "
            f"attempted={attempted_depth} root={root_completed}/{root_total} "
            f"root_pct={root_pct:.1f}% nodes={self.nodes} elapsed_ms={elapsed_ms:.1f} "
            f"tmax_ms={self.tmax_ms} fallback={quality}"
        )
        if self.telemetry is not None:
            try:
                self.telemetry(msg)
            except Exception:
                pass
        if self.audit is not None:
            self.audit.event(
                "sargon_guardrail", kind=kind, target_depth=self.depth,
                attempted_depth=attempted_depth, completed_depth=completed_depth,
                root_completed=root_completed, root_total=root_total, root_pct=root_pct,
                nodes=self.nodes, elapsed_ms=elapsed_ms, tmax_ms=self.tmax_ms,
            )

    def _root_iteration(self, board: chess.Board, legal: list[chess.Move], depth: int,
                        root: chess.Color) -> tuple[list[tuple[int, chess.Move]], bool]:
        scored: list[tuple[int, chess.Move]] = []
        try:
            self._check_deadline()
            for move in legal:
                self._check_deadline()
                value = self._score_root_move(board, move, depth, root)
                scored.append((int(value), move))
            self._check_deadline()
            return scored, True
        except SearchTimeout:
            return scored, False

    def _prepare_search(self) -> None:
        """Reset per-move search state.  SARGON+ extends this hook."""
        self._tt.clear()

    def _iteration(self, board: chess.Board, legal: list[chess.Move], depth: int,
                   root: chess.Color, previous_score: int | None = None) -> tuple[list[tuple[int, chess.Move]], bool]:
        """Run one complete root level.  Subclasses may override the algorithm,
        but the timeout policy lives in SargonCore and is therefore inherited.
        """
        return self._root_iteration(board, legal, depth, root)

    def _after_level_complete(self, board: chess.Board, scored: list[tuple[int, chess.Move]],
                              depth: int, root: chess.Color) -> None:
        """Subclass hook invoked only after a *complete* level."""
        return None

    def _emit_mandatory_level_overrun(self, *, elapsed_ms: float, root_total: int) -> None:
        """Depth 1 is mandatory and is never interrupted by the internal tmax.

        Crossing tmax while completing that safe level is not a guardrail: there
        is no missing analysis inside the level.  The exclamation mark deliberately
        distinguishes this condition from a partial higher-level GUARDRAIL.
        """
        msg = (
            f"❗ BASELEVEL {self.name} time: levels=1/{self.depth} root={root_total}/{root_total} "
            f"root_pct=100.0% nodes={self.nodes} elapsed_ms={elapsed_ms:.1f} "
            f"tmax_ms={self.tmax_ms} action=stop-after-mandatory-level"
        )
        if self.telemetry is not None:
            try:
                self.telemetry(msg)
            except Exception:
                pass
        if self.audit is not None:
            self.audit.event(
                "sargon_mandatory_level_overrun", target_depth=self.depth,
                completed_depth=1, root_total=root_total, root_completed=root_total,
                root_pct=100.0, nodes=self.nodes, elapsed_ms=elapsed_ms,
                tmax_ms=self.tmax_ms,
            )

    def choose(self, board: chess.Board) -> MoveChoice:
        """Anytime-safe SARGON core.

        Invariant introduced in v0.6.21:
        * depth 1 is always completed, regardless of internal ``tmax``;
        * only levels >=2 are interruptible;
        * a partial higher level never replaces the last complete level.

        ``tmax`` remains a total per-move budget.  Consequently, after depth 1
        completes, the remaining budget is exactly ``tmax - elapsed(depth1)``.
        """
        legal = list(board.legal_moves)
        if not legal:
            return MoveChoice(None, self._static(board, board.turn), self.depth, 0, 0.0, self.name)

        start = time.monotonic()
        self.nodes = 0
        self._deadline = None
        self._prepare_search()
        root = board.turn
        legal.sort(key=lambda m: self._move_order_score(board, m), reverse=True)

        completed: list[tuple[int, chess.Move]] | None = None
        completed_depth = 0
        attempted_depth = 1
        partial_count = 0
        timed_out = False
        previous_score: int | None = None

        # Mandatory safe level: deliberately NO deadline.
        scored, complete = self._iteration(board, legal, 1, root, previous_score)
        if not complete:
            # With no internal deadline this path should be unreachable.  Do not
            # silently manufacture a move from partial scores.
            raise PlayerError("SARGON depth 1 no pudo completarse sin deadline interno")
        completed = scored
        completed_depth = 1
        partial_count = len(scored)
        if scored:
            previous_score = max(v for v, _ in scored)
            self._after_level_complete(board, scored, 1, root)

        elapsed_after_d1_ms = (time.monotonic() - start) * 1000.0

        # If the mandatory safe level consumed the whole budget (or more), stop
        # immediately.  This is complete work, therefore ❗ rather than GUARDRAIL.
        budget_exhausted_by_d1 = (
            self.tmax_ms is not None and elapsed_after_d1_ms >= float(self.tmax_ms)
        )
        if budget_exhausted_by_d1:
            self._emit_mandatory_level_overrun(
                elapsed_ms=elapsed_after_d1_ms, root_total=len(legal)
            )
        elif self.depth > 1:
            # tmax is a TOTAL budget measured from move start.  Starting the
            # deadline only now protects D1 while naturally deducting its cost.
            self._deadline = (
                None if self.tmax_ms is None
                else start + float(self.tmax_ms) / 1000.0
            )
            for current_depth in range(2, self.depth + 1):
                attempted_depth = current_depth
                scored, complete = self._iteration(
                    board, legal, current_depth, root, previous_score
                )
                partial_count = len(scored)
                if not complete:
                    timed_out = True
                    break
                completed = scored
                completed_depth = current_depth
                if scored:
                    previous_score = max(v for v, _ in scored)
                    self._after_level_complete(board, scored, current_depth, root)

        elapsed_ms = (time.monotonic() - start) * 1000.0
        self._deadline = None

        if timed_out:
            self._emit_guardrail(
                attempted_depth=attempted_depth, completed_depth=completed_depth,
                root_completed=partial_count, root_total=len(legal), elapsed_ms=elapsed_ms,
            )

        # D1 is guaranteed complete, so there is always a trustworthy choice.
        if not completed:
            raise PlayerError("SARGON invariant violation: no complete depth-1 result")

        best_score = max(v for v, _ in completed)
        pool = [m for v, m in completed if v == best_score]
        move = self.rng.choice(pool)
        score_white = best_score if root == chess.WHITE else -best_score
        if self.audit is not None:
            self.audit.event(
                "sargon_iterative_result", target_depth=self.depth,
                completed_depth=completed_depth, attempted_depth=attempted_depth,
                timed_out=timed_out, mandatory_level_overrun=budget_exhausted_by_d1,
                root_total=len(legal), nodes=self.nodes, elapsed_ms=elapsed_ms,
                bestmove=move.uci(), score_white_cp=int(score_white),
            )
        return MoveChoice(move, int(score_white), completed_depth, self.nodes, elapsed_ms, self.name)


# Backwards-compatible public name.  SargonCore *is* the canonical SARGON player.
SargonPlayer = SargonCore
