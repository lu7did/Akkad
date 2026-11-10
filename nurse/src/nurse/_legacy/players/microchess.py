"""Microchess v0.3.2: same JANUS/STRATGY move policy for every evaluator.

A modern deeper-search extension uses the selected evaluator at the horizon.
The historical candidate computation never depends on evaluator type.
Primary node counts retain the common benchmark contract; additional work
is measured separately in ``last_metrics`` (not falsely reported as nodes).
"""
from __future__ import annotations
from collections import Counter
import time
import chess
from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP
from ..evaluators.microchess import PieceTable, gnm, Janus, measure

class _Deadline(Exception):
    pass

class MicrochessPlayer(Player):
    name = 'MICROCHESS'
    version = '0.3.2'

    def __init__(self, evaluator, depth=2, qdepth=0, tmax_ms=15000, telemetry=None):
        if int(depth) < 1 or int(qdepth) < 0:
            raise PlayerError('microchess: depth>=1, qdepth>=0')
        self.evaluator = evaluator
        self.depth = int(depth)
        self.qdepth = int(qdepth)
        self.tmax_ms = max(1, int(tmax_ms or 15000))
        self.telemetry = telemetry
        self.nodes = 0
        self.last_metrics = {}
        self._table = None

    def _check(self):
        if time.monotonic() > self.deadline:
            raise _Deadline()

    def _moves(self, board):
        return list(gnm(board, board.turn, table=self._table, metrics=self._stats))

    def _static(self, board, ply):
        if board.is_checkmate():
            return -MATE_CP + ply
        if (board.is_stalemate() or board.is_insufficient_material()
                or board.is_seventyfive_moves() or board.is_fivefold_repetition()):
            return 0
        t0 = time.monotonic()
        try:
            self._stats['eval_calls'] += 1
            return int(self.evaluator.evaluate(board)) * (1 if board.turn else -1)
        finally:
            self._stats['eval_time_ms'] += (time.monotonic() - t0) * 1000.0

    def _candidate_scores(self, board, moves):
        """Unconditionally apply JANUS for every evaluator; cached per position.

        Cache is local to a choose(), avoiding stale records across games or
        changing network weights. A position's FEN is used together with the
        candidate move; paths sharing FEN are intentionally reused within the
        current decision only.
        """
        key = board.fen()
        # Reference measurements are invariant across candidates of the same
        # position. Cache only for this choose() invocation.
        reference_key=(key, board.turn)
        if reference_key not in self._reference_cache:
            self._reference_cache[reference_key] = measure(board, board.turn, self._table, self._stats)
            self._stats['reference_cache_misses'] += 1
        else:
            self._stats['reference_cache_hits'] += 1
        previous = self._reference_cache[reference_key]
        scored = []
        for m in moves:
            self._check()
            cache_key = (key, m.uci())
            if cache_key in self._candidate_cache:
                self._stats['candidate_cache_hits'] += 1
                value = self._candidate_cache[cache_key]
            else:
                t0 = time.monotonic()
                try:
                    value = Janus(board, table=self._table,
                                  exchange_branch=2, metrics=self._stats).candidate(m, previous=previous)
                finally:
                    self._stats['janus_time_ms'] += (time.monotonic()-t0)*1000.0
                self._stats['candidate_calls'] += 1
                self._candidate_cache[cache_key] = value
            scored.append((value, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _qsearch(self, board, left, alpha, beta, ply):
        self.nodes += 1
        self._check()
        if board.is_game_over(claim_draw=False):
            return self._static(board, ply)
        in_check = board.is_check()
        if left <= 0:
            return self._static(board, ply)
        if not in_check:
            stand_pat = self._static(board, ply)
            if stand_pat >= beta:
                return stand_pat
            alpha = max(alpha, stand_pat)
        moves = self._moves(board)
        if not in_check:
            moves = [m for m in moves if board.is_capture(m) or m.promotion]
        if not moves:
            return self._static(board, ply) if in_check else alpha
        for m in moves:
            self._check()
            self._table.push(m, board)
            board.push(m)
            try:
                v = -self._qsearch(board, left-1, -beta, -alpha, ply+1)
            finally:
                board.pop()
                self._table.pop()
            if v >= beta:
                return v
            alpha = max(alpha, v)
        return alpha

    def _search(self, board, depth, alpha, beta, ply):
        self.nodes += 1
        self._check()
        if board.is_game_over(claim_draw=False):
            return self._static(board, ply)
        if depth <= 0:
            return self._qsearch(board, self.qdepth, alpha, beta, ply)
        moves = self._moves(board)
        if not moves:
            return self._static(board, ply)
        ranked = self._candidate_scores(board, moves)
        best = -MATE_CP-1
        for immediate, m in ranked:
            self._check()
            self._table.push(m, board)
            board.push(m)
            try:
                if depth == 1:
                    # Same definition for every evaluator, including Microchess:
                    # STRATGY candidate + independently selected leaf evaluator.
                    continuation = -self._qsearch(board, self.qdepth,
                                                  -MATE_CP-1, MATE_CP+1, ply+1)
                else:
                    continuation = -self._search(board, depth-1,
                                                 -MATE_CP-1, MATE_CP+1, ply+1)
            finally:
                board.pop()
                self._table.pop()
            value = (immediate + continuation) // 2
            best = max(best, value)
            alpha = max(alpha, value)
            # Mixed candidate/continuation scores do not share raw child
            # alpha-beta bounds; do not prune on these mixed values.
        return best

    def choose(self, board):
        start = time.monotonic()
        self.deadline = start + self.tmax_ms/1000.0
        self.nodes = 0
        self._stats = Counter()
        self._candidate_cache = {}
        self._reference_cache = {}
        self._table = PieceTable(board)
        original_fen = board.fen()
        best = None
        score = 0
        completed = 0
        try:
            moves = self._moves(board)
            if not moves:
                return MoveChoice(None, 0, 0, 0, 0.0, self.name)
            best = moves[0]
            # Root scores are expensive. Evaluate once, reuse across iterations.
            ranked = self._candidate_scores(board, moves)
            for d in range(1, self.depth+1):
                candidate = None
                value = -MATE_CP-1
                for immediate, m in ranked:
                    self._check()
                    self._table.push(m, board)
                    board.push(m)
                    try:
                        if d == 1:
                            continuation = -self._qsearch(board, self.qdepth,
                                                          -MATE_CP-1, MATE_CP+1, 1)
                        else:
                            continuation = -self._search(board, d-1,
                                                         -MATE_CP-1, MATE_CP+1, 1)
                    finally:
                        board.pop()
                        self._table.pop()
                    result = (immediate + continuation) // 2
                    if result > value:
                        candidate, value = m, result
                if candidate is not None:
                    best, score, completed = candidate, value, d
        except _Deadline:
            pass
        finally:
            self.last_metrics = dict(self._stats)
            self.last_metrics['search_nodes'] = self.nodes
            self.last_metrics['wall_time_ms'] = (time.monotonic()-start)*1000.0
            self.last_metrics['historical_candidate_cache_entries'] = len(self._candidate_cache)
            self.last_metrics['reference_cache_entries'] = len(self._reference_cache)
            if board.fen() != original_fen or self._table._undos:
                raise PlayerError('microchess: board or piece table not restored')
        return MoveChoice(best, int(score if board.turn else -score), completed,
                          self.nodes, (time.monotonic()-start)*1000.0, self.name)
