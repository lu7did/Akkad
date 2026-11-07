"""Sargon Micro v0.1.21 clean baseline: negamax alpha-beta + bounded quiescence.
No TT, PVS, LMR, killers, history heuristics, or watermark/profiling.
Only the last COMPLETED iterative-deepening result is used on timeout.
"""
import gc
import time

if hasattr(time, 'ticks_ms'):
    now = time.ticks_ms
    delta = time.ticks_diff
else:
    now = lambda: int(time.monotonic() * 1000)
    delta = lambda a, b: a-b

INF = 1000000
MATE = 30000

class Timeout(Exception):
    pass

class Engine:
    def __init__(self, net):
        self.net = net
        self.nodes = 0
        self.deadline = 0
        self.cancel = None
        self.qdepth = 4
        self.mem_low = None
        self.mem_samples = 0

    def _clock(self):
        if self.cancel is not None and self.cancel():
            raise Timeout()
        if delta(now(), self.deadline) >= 0:
            raise Timeout()

    def _score(self, b):
        return self.net.evaluate(b) * b.turn

    def _terminal(self, b, ply):
        if b.halfmove >= 150 or b.is_fivefold() or b.insufficient_material():
            return 0
        if b.halfmove >= 100 or b.repetition_count() >= 3:
            return 0
        return None

    def _search(self, b, depth, qleft, alpha, beta, ply):
        self.nodes += 1
        self._clock()
        draw = self._terminal(b, ply)
        if draw is not None:
            return draw
        checked = b.in_check()
        moves = b.legal()
        if not moves:
            return -MATE + ply if checked else 0
        if depth <= 0:
            if checked:
                if ply >= 24:
                    return self._score(b)
                if qleft <= 0:
                    qleft = 1
            else:
                standing = self._score(b)
                if standing >= beta:
                    return standing
                if standing > alpha:
                    alpha = standing
                if qleft <= 0:
                    return alpha
                moves = [m for m in moves if b.is_capture(m) or m[2]]
                if not moves:
                    return alpha
        for m in moves:
            b.push(m)
            try:
                v = -self._search(b, depth-1 if depth > 0 else 0,
                                  qleft if depth > 0 else qleft-1,
                                  -beta, -alpha, ply+1)
            finally:
                b.pop()
            if v > alpha:
                alpha = v
            if alpha >= beta:
                break
        return alpha

    def bestmove(self, b, budget_ms=15000, cancel=None):
        gc.collect()
        moves = b.legal()
        if not moves:
            return None, 0, 0
        gc.collect()
        self.nodes = 0
        self.cancel = cancel
        self.mem_low = None
        self.mem_samples = 0
        self.deadline = now() + max(1, int(budget_ms))
        best = moves[0]
        value = 0
        completed = 0
        for depth in (1, 2, 3, 4):
            try:
                top = -INF
                choice = None
                for m in moves:
                    self._clock()
                    b.push(m)
                    try:
                        v = -self._search(b, depth-1, self.qdepth, -INF, INF, 1)
                    finally:
                        b.pop()
                    if v > top:
                        top, choice = v, m
                if choice is not None:
                    best, value, completed = choice, top, depth
            except Timeout:
                break
            except MemoryError:
                gc.collect()
                break
        return best, value, completed
