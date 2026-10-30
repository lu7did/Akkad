"""KERAS: full-width minimax, nodes=plies, batched leaf evaluation."""
from __future__ import annotations
import time
import chess
from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP


class KerasPlayer(Player):
    name = "KERAS"

    def __init__(self, evaluator, telemetry=None, nodes=1):
        self.evaluator = evaluator
        self.telemetry = telemetry
        self.plies = int(nodes)
        if self.plies < 1:
            raise PlayerError("player=keras requiere nodes >= 1 (profundidad en plies)")

    @staticmethod
    def _terminal(board):
        if board.is_checkmate():
            return -MATE_CP if board.turn == chess.WHITE else MATE_CP
        if board.is_game_over(claim_draw=True):
            return 0
        return None

    def _evaluate_children(self, board, moves, depth, stats):
        """Return WHITE-relative values for each child, preserving move order."""
        values = [None] * len(moves)
        positions, indices = [], []
        for i, move in enumerate(moves):
            board.push(move)
            try:
                terminal = self._terminal(board)
                if terminal is not None:
                    values[i] = terminal
                elif depth == 0:
                    positions.append(board.copy(stack=True))
                    indices.append(i)
                else:
                    values[i] = self._search(board, depth, stats)
            finally:
                board.pop()

        if positions:
            batch = getattr(self.evaluator, 'evaluate_batch', None)
            if callable(batch):
                predicted = list(batch(positions))
                stats['batches'] += 1
                if len(predicted) != len(positions):
                    raise PlayerError(f'evaluate_batch devolvio {len(predicted)} resultados para {len(positions)} posiciones')
            else:
                predicted = [self.evaluator.evaluate(p) for p in positions]
            for i, value in zip(indices, predicted):
                values[i] = int(value)
            stats['evals'] += len(positions)
        stats['nodes'] += len(moves)
        return values

    def _search(self, board, depth, stats):
        terminal = self._terminal(board)
        if terminal is not None:
            return terminal
        if depth <= 0:
            stats['evals'] += 1
            return int(self.evaluator.evaluate(board))
        moves = list(board.legal_moves)
        if not moves:
            return self._terminal(board) or 0
        vals = self._evaluate_children(board, moves, depth - 1, stats)
        return max(vals) if board.turn == chess.WHITE else min(vals)

    def choose(self, board: chess.Board) -> MoveChoice:
        started = time.perf_counter()
        moves = list(board.legal_moves)
        if not moves:
            return MoveChoice(None, 0, self.plies, 0, 0, 'KERAS')
        side = board.turn
        stats = {'evals': 0, 'nodes': 0, 'batches': 0}
        vals = self._evaluate_children(board, moves, self.plies - 1, stats)
        index = max(range(len(vals)), key=vals.__getitem__) if side == chess.WHITE else min(range(len(vals)), key=vals.__getitem__)
        best = moves[index]
        if best not in board.legal_moves:
            raise PlayerError('bestmove ilegal')
        score = int(vals[index]) if side == chess.WHITE else -int(vals[index])
        elapsed = (time.perf_counter() - started) * 1000
        if self.telemetry:
            self.telemetry(f'♟️ KERAS plies={self.plies} legal={len(moves)} nodes={stats["nodes"]} evals={stats["evals"]} batches={stats["batches"]} best={best.uci()} cp={score} ms={elapsed:.1f}')
        return MoveChoice(best, score, self.plies, stats['nodes'], elapsed, 'KERAS')
