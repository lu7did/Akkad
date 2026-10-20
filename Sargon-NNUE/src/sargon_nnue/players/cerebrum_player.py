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
#* cerebrum_player.py
#* Implementa el jugador cerebrum player
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import time
import chess

from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP


class CerebrumPlayer(Player):
    """Native one-ply Cerebrum-style player.

    The official Cerebrum demonstration engine examines every legal move and
    chooses the child with the best NNUE evaluation. This implementation keeps
    that one-ply horizon, but strengthens it operationally by:
      * resolving checkmate/draw terminal children exactly;
      * evaluating every legal move (no pruning at ply=1);
      * using the evaluator's high-precision detailed score when available;
      * reusing Cerebrum first-layer accumulators incrementally when the
        evaluator exposes that capability;
      * deterministic tactical tie-breaking only after evaluator equality.

    The player remains evaluator-agnostic: with a generic evaluator it falls
    back to the common evaluate(board)->White-cp contract.
    """

    name = "CEREBRUM"

    def __init__(self, evaluator, depth: int = 1, qdepth: int = 0):
        self.evaluator = evaluator
        # This player is deliberately fixed to the Cerebrum-equivalent 1 ply.
        # Keep the constructor parameter for factory compatibility, but reject
        # values that could misleadingly suggest a deeper implementation.
        if int(depth) < 1:
            raise PlayerError("CEREBRUM requiere depth >= 1; actualmente opera a 1 ply")
        self.depth = 1
        self.qdepth = int(qdepth)
        if self.qdepth < 0:
            raise PlayerError("CEREBRUM requiere qdepth >= 0")

    @staticmethod
    def _terminal_white_score(board: chess.Board) -> int | None:
        if board.is_checkmate():
            # Side to move is mated.
            return -MATE_CP if board.turn == chess.WHITE else MATE_CP
        if board.is_game_over(claim_draw=True):
            outcome = board.outcome(claim_draw=True)
            if outcome is None or outcome.winner is None:
                return 0
            return MATE_CP if outcome.winner == chess.WHITE else -MATE_CP
        return None

    def _quiescence(self, board: chess.Board, depth: int, alpha: float,
                    beta: float, parent_detail, detailed_fn, incremental_fn,
                    count_node) -> tuple[float, float]:
        """Negamax quiescence, with scores in side-to-move perspective.

        Returns (side_to_move_score, white_score). The second component
        corresponds to the minimax result, not necessarily a static leaf.
        The state passed to incremental inference always belongs to the
        actual parent board, including captures and promotions.
        """
        count_node()
        terminal = self._terminal_white_score(board)
        if terminal is not None:
            v = float(terminal)
            return (v if board.turn == chess.WHITE else -v), v

        if parent_detail is not None and callable(incremental_fn):
            detail = incremental_fn(board, parent_detail)
            white = float(getattr(detail, "score_white_float_cp", detail.score_cp))
        elif callable(detailed_fn) and callable(incremental_fn):
            detail = detailed_fn(board)
            white = float(getattr(detail, "score_white_float_cp", detail.score_cp))
        else:
            detail = None
            white = float(self.evaluator.evaluate(board))

        stand_pat = white if board.turn == chess.WHITE else -white
        in_check = board.is_check()
        # With no check and no budget, this is a quiet leaf.
        if depth <= 0 and not in_check:
            return stand_pat, white

        if not in_check:
            if stand_pat >= beta:
                return stand_pat, white
            if stand_pat > alpha:
                alpha = stand_pat
            best = stand_pat
            best_white = white
            moves = [m for m in board.legal_moves
                     if board.is_capture(m) or m.promotion]
        else:
            # Stand-pat is illegal while in check. All evasions are searched.
            best = float('-inf')
            best_white = white
            moves = list(board.legal_moves)

        # Deterministic tactical order; no extra heuristic borrowed from Sargon+.
        moves.sort(key=lambda m: (int(m.promotion is not None),
                                  int(board.is_capture(m)), m.uci()), reverse=True)
        for move in moves:
            board.push(move)
            try:
                if depth > 0:
                    child_score, child_white = self._quiescence(
                        board, depth - 1, -beta, -alpha,
                        detail, detailed_fn, incremental_fn, count_node)
                    score = -child_score
                else:
                    # Exhausted budget in check: examine each legal evasion
                    # without extending another level (bounded search).
                    count_node()
                    value = self._terminal_white_score(board)
                    if value is not None:
                        child_white = float(value)
                    elif detail is not None and callable(incremental_fn):
                        d = incremental_fn(board, detail)
                        child_white = float(getattr(d, "score_white_float_cp", d.score_cp))
                    else:
                        child_white = float(self.evaluator.evaluate(board))
                    score = child_white if not board.turn == chess.WHITE else -child_white
            finally:
                board.pop()
            if score > best:
                best = score
                best_white = child_white
            if best >= beta:
                break
            if best > alpha:
                alpha = best
        return best, best_white

    def choose(self, board: chess.Board) -> MoveChoice:
        start = time.perf_counter()
        legal = list(board.legal_moves)
        if not legal:
            return MoveChoice(
                move=None,
                score_cp=self._terminal_white_score(board) or 0,
                depth=1,
                nodes=0,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                source=self.name,
            )

        root = board.turn
        detailed_fn = getattr(self.evaluator, "evaluate_detailed", None)
        incremental_fn = getattr(self.evaluator, "evaluate_incremental", None)
        parent_detail = None
        if callable(detailed_fn) and callable(incremental_fn):
            parent_detail = detailed_fn(board)

        best_move: chess.Move | None = None
        best_white_cp = 0
        best_root_value: float | None = None
        best_tie: tuple[int, int, int, str] | None = None
        nodes = 0

        def count_qnode():
            nonlocal nodes
            nodes += 1

        for move in legal:
            board.push(move)
            try:
                nodes += 1
                terminal = self._terminal_white_score(board)
                precise_white_cp: float
                if terminal is not None:
                    white_cp = terminal
                    precise_white_cp = float(terminal)
                elif parent_detail is not None:
                    detail = incremental_fn(board, parent_detail)
                    white_cp = int(detail.score_cp)
                    precise_white_cp = float(
                        getattr(detail, "score_white_float_cp", white_cp)
                    )
                else:
                    white_cp = int(self.evaluator.evaluate(board))
                    precise_white_cp = float(white_cp)

                if self.qdepth > 0 and terminal is None:
                    # A root move consumes the 1-ply search, not the qdepth
                    # budget. Quiescence begins at its resulting position.
                    stm_score, _ = self._quiescence(
                        board, self.qdepth, float('-inf'), float('inf'),
                        parent_detail, detailed_fn, incremental_fn, count_qnode)
                    # At this node the side to move is the root's opponent.
                    root_value = -stm_score
                    precise_white_cp = root_value if root == chess.WHITE else -root_value
                    white_cp = int(precise_white_cp)
                else:
                    root_value = precise_white_cp if root == chess.WHITE else -precise_white_cp
                child_is_check = board.is_check()
            finally:
                board.pop()

            promotion = 1 if move.promotion else 0
            capture = 1 if board.is_capture(move) else 0
            tie = (promotion, 1 if child_is_check else 0, capture, move.uci())

            if (
                best_root_value is None
                or root_value > best_root_value
                or (root_value == best_root_value and (best_tie is None or tie > best_tie))
            ):
                best_root_value = root_value
                best_white_cp = white_cp
                best_move = move
                best_tie = tie

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return MoveChoice(
            move=best_move,
            score_cp=int(best_white_cp),
            depth=1,
            nodes=nodes,
            elapsed_ms=elapsed_ms,
            source=self.name,
        )
