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
#* sargon_plus.py
#* Implementa el jugador Sargon Plus y su busqueda
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import math
import statistics
import time
from collections import deque, Counter
from dataclasses import dataclass

import chess

from .sargon import PIECE, SargonCore, SearchTimeout
from .base import PlayerError
from ..types import MoveChoice, MATE_CP

INF = 2 * MATE_CP

# v0.6.21: --boost is an independent 16-bit mask.  The historical
# optimization numbers 1..13 map directly to bits 0..12 so every existing
# algorithm remains individually addressable.  Bits 14..15 are reserved after the new level-14 feature.
BOOST_FEATURES = {
    1: (0x0001, "history-heuristic"),
    2: (0x0002, "killer-moves"),
    3: (0x0004, "pvs-negascout"),
    4: (0x0008, "tt-bounds"),
    5: (0x0010, "hash-move-first"),
    6: (0x0020, "see-pruning"),
    7: (0x0040, "aspiration-windows"),
    8: (0x0080, "late-move-reductions"),
    9: (0x0100, "futility-reverse-futility"),
    10: (0x0200, "delta-pruning-qsearch"),
    11: (0x0400, "razoring"),
    12: (0x0800, "null-move-pruning"),
    13: (0x1000, "probcut-multicut"),
    14: (0x2000, "incremental-eval"),
}
BOOST_KNOWN_MASK = sum(mask for mask, _ in BOOST_FEATURES.values())

# Turbo mask registry.  v0.6.21 establishes the stable mask/interface and
# monitoring state.  The two actuators are intentionally staged for subsequent
# releases after SargonCore parity is validated.
TURBO_FEATURES = {
    1: (0x01, "adaptive-full-width"),
    2: (0x02, "adaptive-candidate-selection"),
}
TURBO_KNOWN_MASK = sum(mask for mask, _ in TURBO_FEATURES.values())



@dataclass(slots=True)
class TTEntry:
    depth: int
    value: int
    flag: str  # EXACT / LOWER / UPPER
    move: chess.Move | None = None


class SargonPlusPlayer(SargonCore):
    """SargonCore plus independently masked search/resource optimizations.

    ``--boost`` is a 16-bit independent feature mask. ``--turbo`` is an 8-bit
    resource-adaptation mask.  With both masks at zero this class deliberately
    falls through to SargonCore behaviour, providing the parity baseline.
    """

    name = "SARGON-PLUS"

    def __init__(self, evaluator, depth: int = 2, qdepth: int = 2,
                 tmax_ms: int | None = 15000, seed: int | None = None,
                 boost: int = 0, turbo: int = 0, telemetry=None, audit=None):
        super().__init__(
            evaluator, depth, qdepth=qdepth, tmax_ms=tmax_ms, seed=seed,
            iterative_deepening=True, telemetry=telemetry, audit=audit,
        )
        if not 0 <= int(boost) <= 0xFFFF:
            raise PlayerError("boost debe caber en una máscara de 16 bits (0..65535)")
        if not 0 <= int(turbo) <= 0xFF:
            raise PlayerError("turbo debe caber en una máscara de 8 bits (0..255)")
        self.boost = int(boost)
        self.turbo = int(turbo)
        # Opaque evaluator-owned state, not tied to a specific network.
        self._incremental_previous = None
        self._boost_audit_counters = Counter()
        self._turbo_audit_counters = Counter()
        self._boost_audit_run = 0
        self._history: dict[tuple[chess.Color, int, int, int | None], int] = {}
        self._killers: dict[int, list[chess.Move]] = {}
        self._tt2: dict[tuple, TTEntry] = {}
        self._root_best: chess.Move | None = None
        # TURBO cost model is intentionally empirical.  Ratios are learned from
        # actual wall-clock costs of consecutive full-width levels; partial
        # timed-out levels contribute a censored t/p estimate.  No fixed
        # branching-factor threshold is embedded here.
        self._turbo_growth_samples: deque[float] = deque(maxlen=8)
        # Relative error actual/projected for completed (or censored-estimated)
        # full-width levels.  Candidate admission uses the worst recent
        # under-prediction as an empirical safety factor; no fixed time margin.
        self._turbo_projection_error_samples: deque[float] = deque(maxlen=8)

    def _root_eval(self, board: chess.Board, root: chess.Color) -> int:
        """Request optional incremental inference without knowing evaluator type.

        The evaluator owns its cache, precision and fallback semantics.
        Sargon-Plus only keeps an opaque state from the previous evaluation.
        Terminal states are filtered by SargonCore._static before this call.
        """
        if not self._enabled(14):
            return super()._root_eval(board, root)

        score_white, state = self.evaluator.evaluate_with_hint(
            board, incremental=True, previous_state=self._incremental_previous
        )
        self._incremental_previous = state
        self._audit_boost(14, 'hint_requests')
        if state is not None:
            self._audit_boost(14, 'state_returned')
        return int(score_white) if root == chess.WHITE else -int(score_white)

    def _audit_boost(self, level, metric, amount=1):
        if self.audit is not None and getattr(self.audit, 'enabled', False):
            self._boost_audit_counters[f'{level}:{metric}'] += amount

    def _enabled(self, level: int) -> bool:
        try:
            mask = BOOST_FEATURES[int(level)][0]
        except (KeyError, ValueError):
            return False
        active = bool(self.boost & mask)
        if active:
            self._audit_boost(level, 'condition_checks')
        return active

    def _audit_turbo(self, feature, metric, amount=1):
        if self.audit is not None and getattr(self.audit, 'enabled', False):
            self._turbo_audit_counters[f'{feature}:{metric}'] += amount

    def _audit_summary(self):
        """Explicit coverage manifest: absent counters are NOT proof of no opportunity."""
        return {
            'boost': {
                f'0x{mask:04x}': {
                    'name': name, 'enabled': bool(self.boost & mask),
                    'counters': {k.split(':', 1)[1]: v for k, v in self._boost_audit_counters.items()
                                 if k.startswith(f'{level}:')},
                }
                for level, (mask, name) in BOOST_FEATURES.items()
            },
            'turbo': {
                f'0x{mask:02x}': {
                    'name': name, 'enabled': bool(self.turbo & mask),
                    'counters': {k.split(':', 1)[1]: v for k, v in self._turbo_audit_counters.items()
                                 if k.startswith(f'{level}:')},
                }
                for level, (mask, name) in TURBO_FEATURES.items()
            },
            'node_breakdown': 'unavailable: legacy SargonCore qsearch is not instrumented',
        }

    def _turbo_enabled(self, feature: int) -> bool:
        try:
            mask = TURBO_FEATURES[int(feature)][0]
        except (KeyError, ValueError):
            return False
        active = bool(self.turbo & mask)
        if active:
            self._audit_turbo(feature, "condition_checks")
        return active

    def _advanced_boost_enabled(self) -> bool:
        # Features 3..13 need the extensible search path. PVS itself is now
        # conditional inside that path, so unrelated bits do not silently
        # enable PVS.
        return any(self._enabled(level) for level in range(3, 14))

    @staticmethod
    def _tt_key(board: chess.Board) -> tuple:
        # Position information relevant to legal moves and repetition-independent
        # search. Halfmove clock is included because claimable 50-move draws affect
        # terminal status. Fullmove number is intentionally irrelevant.
        ep = board.ep_square if board.has_legal_en_passant() else None
        return (
            board.board_fen(),
            board.turn,
            board.castling_rights,
            ep,
            board.halfmove_clock,
        )

    @staticmethod
    def _history_key(board: chess.Board, move: chess.Move) -> tuple[chess.Color, int, int, int | None]:
        return (board.turn, move.from_square, move.to_square, move.promotion)

    def _record_history(self, board: chess.Board, move: chess.Move, depth: int) -> None:
        if not self._enabled(1) or board.is_capture(move) or move.promotion:
            return
        key = self._history_key(board, move)
        self._history[key] = min(1_000_000, self._history.get(key, 0) + depth * depth)
        self._audit_boost(1, 'history_updates')

    def _record_killer(self, move: chess.Move, ply: int, board: chess.Board) -> None:
        if not self._enabled(2) or board.is_capture(move) or move.promotion:
            return
        killers = self._killers.setdefault(ply, [])
        if move in killers:
            killers.remove(move)
        killers.insert(0, move)
        del killers[2:]
        self._audit_boost(2, "killer_updates")

    def _move_order_score_plus(self, board: chess.Board, move: chess.Move, ply: int,
                               hash_move: chess.Move | None = None) -> float:
        if self._enabled(5) and hash_move is not None and move == hash_move:
            self._audit_boost(5, "hash_move_first")
            return 1_000_000_000.0
        score = self._move_order_score(board, move)
        if self._enabled(2) and not board.is_capture(move) and not move.promotion:
            killers = self._killers.get(ply, ())
            if killers and move == killers[0]:
                score += 1_000_000.0
            elif len(killers) > 1 and move == killers[1]:
                score += 900_000.0
        if self._enabled(1) and not board.is_capture(move) and not move.promotion:
            score += self._history.get(self._history_key(board, move), 0) / 1000.0
        return score

    def _ordered_moves(self, board: chess.Board, ply: int,
                       hash_move: chess.Move | None = None) -> list[chess.Move]:
        moves = list(board.legal_moves)
        # Audit side-channel: compare existing order against the same comparator
        # with disabled features, without modifying the actual sorted result.
        audit_on = self.audit is not None and getattr(self.audit, 'enabled', False)
        if audit_on and self.boost & (0x0001 | 0x0002 | 0x0010):
            baseline = sorted(moves, key=lambda m: self._move_order_score(board, m), reverse=True)
            baseline_top = baseline[0] if baseline else None
        else:
            baseline = None
            baseline_top = None
        moves.sort(key=lambda m: self._move_order_score_plus(board, m, ply, hash_move), reverse=True)
        if baseline is not None and moves:
            for feature in (1, 2, 5):
                mask = BOOST_FEATURES[feature][0]
                if not (self.boost & mask):
                    continue
                # Attribution of ordering changes between simultaneously enabled
                # features is not separable; only rigorous for single-bit tests.
                self._audit_boost(feature, 'ordered_lists')
                if moves != baseline:
                    self._audit_boost(feature, 'ordering_changed_combined')
                if moves[0] != baseline_top:
                    self._audit_boost(feature, 'top_move_changed_combined')
        return moves

    @staticmethod
    def _piece_cp(piece_type: int | None) -> int:
        return {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 20_000,
            None: 0,
        }[piece_type]

    def _captured_piece_type(self, board: chess.Board, move: chess.Move) -> int | None:
        if board.is_en_passant(move):
            return chess.PAWN
        victim = board.piece_at(move.to_square)
        return victim.piece_type if victim else None

    def _see(self, board: chess.Board, move: chess.Move) -> int:
        """Static exchange evaluation for a capture, in centipawns.

        This performs a legal least-valuable-attacker swap sequence on the target
        square.  Promotions and en-passant are handled by the board itself.
        """
        if not board.is_capture(move):
            return 0
        target = move.to_square
        gain0 = self._piece_cp(self._captured_piece_type(board, move))
        if move.promotion:
            gain0 += self._piece_cp(move.promotion) - self._piece_cp(chess.PAWN)
        gains = [gain0]
        board.push(move)
        try:
            while True:
                captures = [m for m in board.legal_moves if m.to_square == target and board.is_capture(m)]
                if not captures:
                    break
                captures.sort(key=lambda m: self._piece_cp((board.piece_at(m.from_square) or chess.Piece(chess.KING, board.turn)).piece_type))
                reply = captures[0]
                attacker = board.piece_at(reply.from_square)
                attacker_value = self._piece_cp(attacker.piece_type if attacker else None)
                if reply.promotion:
                    attacker_value += self._piece_cp(reply.promotion) - self._piece_cp(chess.PAWN)
                gains.append(attacker_value - gains[-1])
                board.push(reply)
            for i in range(len(gains) - 2, -1, -1):
                gains[i] = min(gains[i], -gains[i + 1])
            return int(gains[0])
        finally:
            for _ in range(len(gains) - 1):
                board.pop()
            board.pop()

    def _forcing_moves_plus(self, board: chess.Board, ply: int) -> list[chess.Move]:
        if board.is_check():
            moves = list(board.legal_moves)
        else:
            moves = [m for m in board.legal_moves
                     if board.is_capture(m) or m.promotion is not None or board.gives_check(m)]
        if self._enabled(6) and not board.is_check():
            kept: list[chess.Move] = []
            for m in moves:
                # Checks/promotions remain forcing; prune only losing captures.
                if board.is_capture(m) and not m.promotion and not board.gives_check(m) and self._see(board, m) < 0:
                    self._audit_boost(6, 'see_pruned_qmoves')
                    continue
                kept.append(m)
            moves = kept
        moves.sort(key=lambda m: self._move_order_score_plus(board, m, ply), reverse=True)
        return moves

    def _quiescence_plus(self, board: chess.Board, depth: int, alpha: int, beta: int,
                         root: chess.Color, ply: int) -> int:
        self._check_deadline()
        self.nodes += 1
        stand = self._static(board, root)
        if depth <= 0 or board.is_game_over(claim_draw=True):
            return stand
        in_check = board.is_check()
        moves = self._forcing_moves_plus(board, ply)
        if not moves:
            return stand

        maximizing = board.turn == root
        if maximizing:
            best = -INF if in_check else stand
            if not in_check and best >= beta:
                return int(best)
            if not in_check:
                alpha = max(alpha, best)
            for move in moves:
                if self._enabled(10) and not in_check and board.is_capture(move) and not move.promotion and not board.gives_check(move):
                    victim = self._piece_cp(self._captured_piece_type(board, move))
                    if stand + victim + 120 < alpha:
                        self._audit_boost(10, 'delta_pruned_moves')
                        continue
                board.push(move)
                try:
                    value = self._quiescence_plus(board, depth - 1, alpha, beta, root, ply + 1)
                finally:
                    board.pop()
                best = max(best, value)
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
            return int(best)

        best = INF if in_check else stand
        if not in_check and best <= alpha:
            return int(best)
        if not in_check:
            beta = min(beta, best)
        for move in moves:
            if self._enabled(10) and not in_check and board.is_capture(move) and not move.promotion and not board.gives_check(move):
                victim = self._piece_cp(self._captured_piece_type(board, move))
                if stand - victim - 120 > beta:
                    self._audit_boost(10, 'delta_pruned_moves')
                    continue
            board.push(move)
            try:
                value = self._quiescence_plus(board, depth - 1, alpha, beta, root, ply + 1)
            finally:
                board.pop()
            best = min(best, value)
            beta = min(beta, best)
            if alpha >= beta:
                break
        return int(best)

    def _legacy_search(self, board: chess.Board, depth: int, alpha: int, beta: int,
                       root: chess.Color, ply: int) -> int:
        """Canonical minimax with only ordering heuristics added (boost 0..2)."""
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
        moves = self._ordered_moves(board, ply)
        maximizing = board.turn == root
        best = -INF if maximizing else INF
        for move in moves:
            board.push(move)
            try:
                value = self._legacy_search(board, depth - 1, alpha, beta, root, ply + 1)
            finally:
                board.pop()
            if maximizing:
                best = max(best, value)
                alpha = max(alpha, best)
            else:
                best = min(best, value)
                beta = min(beta, best)
            if alpha >= beta:
                self._record_history(board, move, depth)
                self._record_killer(move, ply, board)
                break
        self._tt[key] = int(best)
        return int(best)

    def _tt_probe(self, board: chess.Board, depth: int, alpha: int, beta: int) -> tuple[int | None, int, int, chess.Move | None]:
        if not self._enabled(4):
            return None, alpha, beta, None
        entry = self._tt2.get(self._tt_key(board))
        if entry is None:
            self._audit_boost(4, "tt_miss")
            return None, alpha, beta, None
        hash_move = entry.move
        self._audit_boost(4, "tt_hit")
        if entry.depth < depth:
            self._audit_boost(4, "tt_shallow")
            return None, alpha, beta, hash_move
        if entry.flag == "EXACT":
            self._audit_boost(4, "tt_exact")
            return entry.value, alpha, beta, hash_move
        if entry.flag == "LOWER":
            alpha = max(alpha, entry.value)
        elif entry.flag == "UPPER":
            beta = min(beta, entry.value)
        if alpha >= beta:
            return entry.value, alpha, beta, hash_move
        return None, alpha, beta, hash_move

    def _tt_store(self, board: chess.Board, depth: int, value: int, alpha0: int, beta0: int,
                  move: chess.Move | None) -> None:
        if not self._enabled(4):
            return
        flag = "EXACT"
        if value <= alpha0:
            flag = "UPPER"
        elif value >= beta0:
            flag = "LOWER"
        key = self._tt_key(board)
        old = self._tt2.get(key)
        if old is None or depth >= old.depth or flag == "EXACT":
            self._tt2[key] = TTEntry(depth, int(value), flag, move)
            self._audit_boost(4, "tt_stores")

    def _can_null_move(self, board: chess.Board, depth: int) -> bool:
        if depth < 3 or board.is_check():
            return False
        # Avoid classic zugzwang-prone pawn-only endings.
        non_pawns = board.knights | board.bishops | board.rooks | board.queens
        return bool(non_pawns & board.occupied_co[board.turn])

    def _pvs(self, board: chess.Board, depth: int, alpha: int, beta: int,
             root: chess.Color, ply: int, allow_null: bool = True) -> int:
        self._check_deadline()
        self.nodes += 1
        if board.is_game_over(claim_draw=True):
            return self._static(board, root)
        if depth <= 0:
            return self._quiescence_plus(board, self.qdepth, alpha, beta, root, ply)

        alpha0, beta0 = alpha, beta
        hit, alpha, beta, hash_move = self._tt_probe(board, depth, alpha, beta)
        if hit is not None:
            self._audit_boost(4, "tt_cutoffs")
            return int(hit)

        maximizing = board.turn == root
        static = None
        if self._enabled(9) or self._enabled(11):
            static = self._static(board, root)

        # Reverse futility pruning: only quiet, non-PV-like nodes.
        if self._enabled(9) and depth <= 3 and not board.is_check() and static is not None:
            margin = 110 * depth
            if maximizing and static - margin >= beta:
                self._audit_boost(9, "reverse_futility_cuts")
                return int(static)
            if not maximizing and static + margin <= alpha:
                self._audit_boost(9, "reverse_futility_cuts")
                return int(static)

        # Razoring near the horizon. Fail-soft qsearch verifies the cheap margin test.
        if self._enabled(11) and depth <= 2 and not board.is_check() and static is not None:
            margin = 180 + 120 * (depth - 1)
            if maximizing and static + margin <= alpha:
                q = self._quiescence_plus(board, self.qdepth, alpha, beta, root, ply)
                self._audit_boost(11, "razor_verifications")
                if q <= alpha:
                    self._audit_boost(11, "razor_cuts")
                    return int(q)
            elif not maximizing and static - margin >= beta:
                q = self._quiescence_plus(board, self.qdepth, alpha, beta, root, ply)
                self._audit_boost(11, "razor_verifications")
                if q >= beta:
                    self._audit_boost(11, "razor_cuts")
                    return int(q)

        # Null-move pruning with a modest reduction and no consecutive nulls.
        if self._enabled(12) and allow_null and self._can_null_move(board, depth):
            self._audit_boost(12, "null_searches")
            reduction = 2 + depth // 6
            board.push(chess.Move.null())
            try:
                null_depth = max(0, depth - 1 - reduction)
                if maximizing:
                    val = self._pvs(board, null_depth, beta - 1, beta, root, ply + 1, False)
                    if val >= beta:
                        self._audit_boost(12, "null_cuts")
                        return int(val)
                else:
                    val = self._pvs(board, null_depth, alpha, alpha + 1, root, ply + 1, False)
                    if val <= alpha:
                        self._audit_boost(12, "null_cuts")
                        return int(val)
            finally:
                board.pop()

        # Conservative ProbCut: verify a tactical capture with a reduced search.
        if self._enabled(13) and depth >= 5 and not board.is_check():
            margin = 180
            tactical = [m for m in self._ordered_moves(board, ply, hash_move) if board.is_capture(m)]
            for move in tactical[:4]:
                self._audit_boost(13, "probcut_probes")
                if self._enabled(6) and self._see(board, move) < 0:
                    continue
                board.push(move)
                try:
                    if maximizing:
                        val = self._pvs(board, depth - 3, beta + margin - 1, beta + margin, root, ply + 1, False)
                        if val >= beta + margin:
                            self._audit_boost(13, "probcut_cuts")
                            return int(val)
                    else:
                        val = self._pvs(board, depth - 3, alpha - margin, alpha - margin + 1, root, ply + 1, False)
                        if val <= alpha - margin:
                            self._audit_boost(13, "probcut_cuts")
                            return int(val)
                finally:
                    board.pop()

        moves = self._ordered_moves(board, ply, hash_move)
        if not moves:
            return self._static(board, root)

        best = -INF if maximizing else INF
        best_move: chess.Move | None = None
        searched = 0
        quiet_tried = 0

        for move in moves:
            is_capture = board.is_capture(move)
            is_quiet = not is_capture and move.promotion is None and not board.gives_check(move)

            # SEE pruning is deliberately shallow and excludes checks/promotions.
            if self._enabled(6) and depth <= 3 and is_capture and not move.promotion and not board.gives_check(move):
                if self._see(board, move) < -90 * depth:
                    self._audit_boost(6, "see_pruned_moves")
                    continue

            # Futility pruning at frontier-ish quiet moves.
            if self._enabled(9) and depth <= 2 and is_quiet and not board.is_check() and static is not None:
                margin = 120 * depth
                if maximizing and static + margin <= alpha:
                    self._audit_boost(9, "futility_pruned_moves")
                    continue
                if not maximizing and static - margin >= beta:
                    self._audit_boost(9, "futility_pruned_moves")
                    continue

            # MultiCut: after several prior moves at sufficiently deep non-check nodes,
            # test up to three remaining moves at reduced depth and cut if two fail high/low.
            if self._enabled(13) and depth >= 6 and searched == 0 and not board.is_check():
                cut_count = 0
                for probe in moves[:3]:
                    self._audit_boost(13, "multicut_probes")
                    board.push(probe)
                    try:
                        if maximizing:
                            pv = self._pvs(board, depth - 3, beta - 1, beta, root, ply + 1, False)
                            cut_count += int(pv >= beta)
                        else:
                            pv = self._pvs(board, depth - 3, alpha, alpha + 1, root, ply + 1, False)
                            cut_count += int(pv <= alpha)
                    finally:
                        board.pop()
                    if cut_count >= 2:
                        self._audit_boost(13, "multicut_cuts")
                        return int(beta if maximizing else alpha)

            reduction = 0
            if self._enabled(8) and depth >= 3 and searched >= 3 and is_quiet and not board.is_check():
                reduction = 1
                self._audit_boost(8, "reduced_moves")
                if depth >= 6 and searched >= 6:
                    reduction = 2

            board.push(move)
            try:
                child_depth = max(0, depth - 1 - reduction)
                if searched == 0 or not self._enabled(3):
                    # Full-window alpha-beta unless the PVS bit is explicitly on.
                    value = self._pvs(board, child_depth, alpha, beta, root, ply + 1, True)
                elif maximizing:
                    self._audit_boost(3, "pvs_probe")
                    # Null-window PVS probe, then full re-search only on improvement.
                    value = self._pvs(board, child_depth, alpha, alpha + 1, root, ply + 1, True)
                    if value > alpha and value < beta:
                        self._audit_boost(3, "pvs_researches")
                        value = self._pvs(board, depth - 1, alpha, beta, root, ply + 1, True)
                else:
                    self._audit_boost(3, 'pvs_probe')
                    value = self._pvs(board, child_depth, beta - 1, beta, root, ply + 1, True)
                    if value < beta and value > alpha:
                        self._audit_boost(3, "pvs_researches")
                        value = self._pvs(board, depth - 1, alpha, beta, root, ply + 1, True)

                # LMR reductions are always verified when they improve the node bound.
                if reduction:
                    if maximizing and value > alpha:
                        self._audit_boost(8, 'full_depth_researches')
                        value = self._pvs(board, depth - 1, alpha, beta, root, ply + 1, True)
                    elif not maximizing and value < beta:
                        self._audit_boost(8, 'full_depth_researches')
                        value = self._pvs(board, depth - 1, alpha, beta, root, ply + 1, True)
            finally:
                board.pop()

            searched += 1
            if is_quiet:
                quiet_tried += 1
            if maximizing:
                if value > best:
                    best, best_move = value, move
                alpha = max(alpha, best)
            else:
                if value < best:
                    best, best_move = value, move
                beta = min(beta, best)
            if alpha >= beta:
                self._record_history(board, move, depth)
                self._record_killer(move, ply, board)
                break

        if searched == 0:
            best = self._quiescence_plus(board, self.qdepth, alpha0, beta0, root, ply)
        self._tt_store(board, depth, int(best), alpha0, beta0, best_move)
        return int(best)

    def _search_child(self, board: chess.Board, move: chess.Move, depth: int,
                      alpha: int, beta: int, root: chess.Color) -> int:
        board.push(move)
        try:
            if board.is_checkmate():
                return MATE_CP
            if not self._advanced_boost_enabled():
                return self._legacy_search(board, max(0, depth - 1), alpha, beta, root, 1)
            return self._pvs(board, max(0, depth - 1), alpha, beta, root, 1)
        finally:
            board.pop()

    def _root_iteration_plus(self, board: chess.Board, depth: int, root: chess.Color,
                             alpha: int = -INF, beta: int = INF) -> tuple[list[tuple[int, chess.Move]], bool]:
        hash_move = self._root_best if self._enabled(5) else None
        legal = self._ordered_moves(board, 0, hash_move)
        scored: list[tuple[int, chess.Move]] = []
        complete = True
        local_alpha = alpha
        try:
            for move in legal:
                self._check_deadline()
                value = self._search_child(board, move, depth, local_alpha, beta, root)
                scored.append((int(value), move))
                local_alpha = max(local_alpha, int(value))
                if local_alpha >= beta:
                    break
        except SearchTimeout:
            complete = False
        return scored, complete

    def _aspiration_iteration(self, board: chess.Board, depth: int, root: chess.Color,
                              previous: int | None) -> tuple[list[tuple[int, chess.Move]], bool]:
        if not self._enabled(7) or previous is None or depth <= 1:
            return self._root_iteration_plus(board, depth, root)
        window = 50
        self._audit_boost(7, 'aspiration_windows')
        while True:
            alpha, beta = previous - window, previous + window
            scored, complete = self._root_iteration_plus(board, depth, root, alpha, beta)
            if not complete or not scored:
                return scored, complete
            best = max(v for v, _ in scored)
            if best <= alpha or best >= beta:
                self._audit_boost(7, 'aspiration_researches')
                window *= 2
                if window >= INF:
                    return self._root_iteration_plus(board, depth, root)
                continue
            return scored, complete

    def _prepare_search(self) -> None:
        super()._prepare_search()
        self._tt2.clear()
        self._history.clear()
        self._killers.clear()
        self._root_best = None

    def _iteration(self, board: chess.Board, legal: list[chess.Move], depth: int,
                   root: chess.Color, previous_score: int | None = None) -> tuple[list[tuple[int, chess.Move]], bool]:
        # Strict parity path: with both masks zero, use the exact SargonCore
        # iteration instead of a merely equivalent reimplementation.
        if self.boost == 0 and self.turbo == 0:
            return super()._iteration(board, legal, depth, root, previous_score)
        # TURBO scheduling is handled by choose().  Once a full-width level has
        # been admitted, the actual search algorithm still depends only on BOOST.
        if self.boost == 0:
            return super()._iteration(board, legal, depth, root, previous_score)
        return self._aspiration_iteration(board, depth, root, previous_score)

    def _after_level_complete(self, board: chess.Board, scored: list[tuple[int, chess.Move]],
                              depth: int, root: chess.Color) -> None:
        if scored and self.audit is not None and getattr(self.audit, 'enabled', False):
            self.audit.event('boost_level_complete', schema=1,
                             search_id=self._boost_audit_run, depth=depth,
                             nodes_total=self.nodes,
                             elapsed_total_ms=round((time.monotonic()-self._boost_audit_start)*1000, 3),
                             root_completed=len(scored),
                             boost_mask=self.boost, turbo_mask=self.turbo)
        if scored:
            best_score = max(v for v, _ in scored)
            best_moves = [m for v, m in scored if v == best_score]
            self._root_best = best_moves[0]

    # ------------------------------------------------------------------
    # TURBO resource controller (v0.6.24)
    # ------------------------------------------------------------------
    def _turbo_emit(self, message: str, **audit_fields) -> None:
        kind = str(audit_fields.get('action') or audit_fields.get('reason') or 'event')
        for feature in (1, 2):
            if self.turbo & TURBO_FEATURES[feature][0]:
                self._audit_turbo(feature, 'emitted_events')
                self._audit_turbo(feature, f'event:{kind}')
        if self.telemetry is not None:
            try:
                self.telemetry(message)
            except Exception:
                pass
        if self.audit is not None:
            try:
                self.audit.event("sargon_turbo", search_id=self._boost_audit_run, **audit_fields)
            except Exception:
                pass

    def _turbo_growth(self) -> float | None:
        """Robust empirical growth estimate, or None while evidence is absent."""
        if not self._turbo_growth_samples:
            return None
        return float(statistics.median(self._turbo_growth_samples))

    def _turbo_observe_ratio(self, previous_ms: float, projected_ms: float) -> None:
        if previous_ms <= 0.0 or projected_ms <= 0.0:
            return
        ratio = projected_ms / previous_ms
        if math.isfinite(ratio) and ratio > 0.0:
            # Large ratios are legitimate; retain them.  Only impossible/noisy
            # near-zero values are rejected by the guards above.
            self._turbo_growth_samples.append(float(ratio))

    def _turbo_project_next_ms(self, last_level_ms: float) -> float | None:
        growth = self._turbo_growth()
        if growth is None or last_level_ms <= 0.0:
            return None
        return float(last_level_ms * growth)

    def _turbo_observe_projection_error(self, projected_ms: float | None, actual_ms: float) -> None:
        """Learn only under-prediction risk from empirical full-width costs.

        The ratio actual/projected is stored when both values are meaningful.
        Values <= 1 are harmless for admission and are retained because they
        describe calibration; the guard factor itself never drops below 1.
        """
        if projected_ms is None or projected_ms <= 0.0 or actual_ms <= 0.0:
            return
        ratio = actual_ms / projected_ms
        if math.isfinite(ratio) and ratio > 0.0:
            self._turbo_projection_error_samples.append(float(ratio))

    def _turbo_projection_guard_factor(self) -> float:
        """Empirical safety factor for entering selective root search.

        Use the worst recent under-prediction.  This is deliberately local to
        candidate admission: it does not alter the median growth estimator or
        the ordinary K formula once selective search has been admitted.
        """
        if not self._turbo_projection_error_samples:
            return 1.0
        return max(1.0, max(self._turbo_projection_error_samples))

    def _turbo_candidate_iteration(self, board: chess.Board,
                                   candidates: list[chess.Move], depth: int,
                                   root: chess.Color) -> tuple[list[tuple[int, chess.Move]], bool]:
        """Search only the admitted root candidates at the requested depth.

        Candidate count is decided by budget before entering this function.  The
        same Core/BOOST child search is used; TURBO does not alter leaf evaluation.
        """
        scored: list[tuple[int, chess.Move]] = []
        local_alpha = -INF
        try:
            for move in candidates:
                self._check_deadline()
                if self.boost == 0:
                    value = self._score_root_move(board, move, depth, root)
                else:
                    value = self._search_child(board, move, depth, local_alpha, INF, root)
                scored.append((int(value), move))
                local_alpha = max(local_alpha, int(value))
        except SearchTimeout:
            return scored, False
        return scored, True

    def choose(self, board: chess.Board) -> MoveChoice:
        # Absolute baseline guarantee: turbo=0 delegates to the canonical Core
        # scheduler unchanged.  BOOST still operates through _iteration().
        if self.turbo == 0:
            # v0.6.89: SargonCore.choose() invokes our _after_level_complete()
            # hook. Initialize its audit context BEFORE delegating, otherwise
            # audit-enabled searches raise AttributeError after depth 1 and the
            # UCI listener replies `bestmove (none)`.
            if self.audit is None or not getattr(self.audit, 'enabled', False):
                return super().choose(board)
            self._boost_audit_run += 1
            self._boost_audit_start = time.monotonic()
            self._boost_audit_counters.clear()
            self._turbo_audit_counters.clear()
            choice = super().choose(board)
            elapsed_ms = (time.monotonic() - self._boost_audit_start) * 1000.0
            self.audit.event(
                'boost_search_metrics', schema=2, search_id=self._boost_audit_run,
                boost_mask=self.boost, turbo_mask=self.turbo,
                requested_depth=self.depth, completed_depth=choice.depth,
                attempted_depth=choice.depth, timed_out=False,
                bestmove=choice.move.uci() if choice.move else None,
                score_white_cp=int(choice.score_cp), root_fen=board.fen(),
                nodes=choice.nodes, elapsed_ms=round(elapsed_ms, 3),
                nps=round(1000 * choice.nodes / elapsed_ms, 2) if elapsed_ms > 0 else None,
                counters=dict(self._boost_audit_counters),
                turbo_counters=dict(self._turbo_audit_counters),
                coverage=self._audit_summary(),
            )
            return choice

        legal = list(board.legal_moves)
        if not legal:
            return MoveChoice(None, self._static(board, board.turn), self.depth, 0, 0.0, self.name)

        start = time.monotonic()
        self._boost_audit_run += 1
        self._boost_audit_start = start
        self._boost_audit_counters.clear()
        self._turbo_audit_counters.clear()
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
        last_level_ms = 0.0
        previous_level_ms: float | None = None
        selective_depth: int | None = None
        selective_count = 0
        turbo_return_reason: str | None = None

        # D1 remains mandatory and uninterruptible exactly as in SargonCore.
        level_start = time.monotonic()
        scored, complete = self._iteration(board, legal, 1, root, previous_score)
        last_level_ms = (time.monotonic() - level_start) * 1000.0
        if not complete:
            raise PlayerError("SARGON+ depth 1 no pudo completarse sin deadline interno")
        completed = scored
        completed_depth = 1
        partial_count = len(scored)
        if scored:
            previous_score = max(v for v, _ in scored)
            self._after_level_complete(board, scored, 1, root)

        elapsed_after_d1_ms = (time.monotonic() - start) * 1000.0
        budget_exhausted_by_d1 = (
            self.tmax_ms is not None and elapsed_after_d1_ms >= float(self.tmax_ms)
        )
        if budget_exhausted_by_d1:
            self._emit_mandatory_level_overrun(elapsed_ms=elapsed_after_d1_ms, root_total=len(legal))
        elif self.depth > 1:
            self._deadline = None if self.tmax_ms is None else start + float(self.tmax_ms) / 1000.0

            for current_depth in range(2, self.depth + 1):
                attempted_depth = current_depth
                now = time.monotonic()
                remaining_ms = math.inf if self._deadline is None else max(0.0, (self._deadline - now) * 1000.0)
                projected_ms = self._turbo_project_next_ms(last_level_ms)

                # If there is no empirical growth evidence yet, remain neutral:
                # start the full level and learn from what actually happens.
                full_width_fits = projected_ms is None or projected_ms <= remaining_ms

                if not full_width_fits and (self._turbo_enabled(1) or self._turbo_enabled(2)):
                    if self._turbo_enabled(1):
                        self._turbo_emit(
                            f"⚡ TURBO full-width SKIP depth={current_depth} projected_ms={projected_ms:.1f} "
                            f"remaining_ms={remaining_ms:.1f} action=do-not-start-full-level",
                            action="full_width_skip", depth=current_depth,
                            projected_ms=projected_ms, remaining_ms=remaining_ms,
                            growth=self._turbo_growth(),
                        )

                    if self._turbo_enabled(2) and completed:
                        n = len(completed)
                        if n > 0 and projected_ms > 0.0 and remaining_ms > 0.0:
                            # Candidate-entry guardrail (v0.6.23).  A selective
                            # level is useful only if at least one root move can
                            # plausibly finish.  Estimate one-root cost from the
                            # projected full-width level, inflate it by TURBO's
                            # worst recent empirical under-prediction, and keep
                            # one root-equivalent from the last completed level
                            # as a data-derived reserve.  No fixed milliseconds or
                            # arbitrary K threshold are introduced.
                            guard_factor = self._turbo_projection_guard_factor()
                            projected_root_ms = projected_ms / n
                            guarded_root_ms = projected_root_ms * guard_factor
                            reserve_ms = last_level_ms / n if last_level_ms > 0.0 else 0.0
                            required_one_ms = guarded_root_ms + reserve_ms
                            if remaining_ms < required_one_ms:
                                self._turbo_emit(
                                    f"⚡ TURBO candidates SKIP depth={current_depth} reason=insufficient-budget-for-one-root "
                                    f"remaining_ms={remaining_ms:.1f} required_ms={required_one_ms:.1f} "
                                    f"projected_root_ms={projected_root_ms:.1f} guard={guard_factor:.3f} "
                                    f"reserve_ms={reserve_ms:.1f}",
                                    action="candidate_skip_insufficient_budget", depth=current_depth,
                                    root_total=n, remaining_ms=remaining_ms,
                                    projected_root_ms=projected_root_ms, guard_factor=guard_factor,
                                    reserve_ms=reserve_ms, required_ms=required_one_ms,
                                )
                                turbo_return_reason = "insufficient-budget-for-one-root"
                                break

                            # v0.6.26 conservative sizing.  First estimate how
                            # many root candidates fit after the dynamic reserve
                            # and empirical under-prediction guard.  Then search
                            # only half of that safe capacity.  Candidate Selection
                            # is useful only if the conservative set contains at
                            # least two roots; a single deepened root provides no
                            # relative comparison at the new level and is skipped.
                            usable_ms = max(0.0, remaining_ms - reserve_ms)
                            safe_k = min(n, int(math.floor(usable_ms / guarded_root_ms)))
                            k = min(n - 1 if n > 1 else 1, safe_k // 2)
                            if k < 2:
                                self._turbo_emit(
                                    f"⚡ TURBO candidates SKIP depth={current_depth} reason=conservative-set-too-small "
                                    f"k={k}/{n} safe_k={safe_k}/{n} remaining_ms={remaining_ms:.1f} "
                                    f"usable_ms={usable_ms:.1f} guarded_root_ms={guarded_root_ms:.1f} "
                                    f"guard={guard_factor:.3f} reserve_ms={reserve_ms:.1f}",
                                    action="candidate_skip_conservative_set_too_small", depth=current_depth,
                                    candidates=k, root_total=n, safe_candidates=safe_k, remaining_ms=remaining_ms,
                                    usable_ms=usable_ms, guarded_root_ms=guarded_root_ms,
                                    guard_factor=guard_factor, reserve_ms=reserve_ms,
                                )
                                turbo_return_reason = "conservative-set-too-small"
                                break

                            fraction = k / n
                            ranked = [m for _, m in sorted(completed, key=lambda vm: vm[0], reverse=True)]
                            candidates = ranked[:k]
                            selective_count = len(candidates)
                            self._turbo_emit(
                                f"⚡ TURBO candidates depth={current_depth} k={k}/{n} safe_k={safe_k}/{n} "
                                f"fraction={fraction:.3f} projected_full_ms={projected_ms:.1f} "
                                f"remaining_ms={remaining_ms:.1f} guard={guard_factor:.3f} "
                                f"reserve_ms={reserve_ms:.1f}",
                                action="candidate_selection", depth=current_depth,
                                candidates=k, safe_candidates=safe_k, root_total=n, fraction=fraction,
                                projected_ms=projected_ms, remaining_ms=remaining_ms,
                                guard_factor=guard_factor, reserve_ms=reserve_ms,
                            )
                            cstart = time.monotonic()
                            cscored, ccomplete = self._turbo_candidate_iteration(
                                board, candidates, current_depth, root
                            )
                            c_ms = (time.monotonic() - cstart) * 1000.0
                            partial_count = len(cscored)
                            if ccomplete and cscored:
                                completed = cscored
                                selective_depth = current_depth
                                best = max(v for v, _ in cscored)
                                previous_score = best
                                self._after_level_complete(board, cscored, current_depth, root)
                                self._turbo_emit(
                                    f"⚡ TURBO candidates COMPLETE depth={current_depth} k={k}/{n} "
                                    f"elapsed_ms={c_ms:.1f}",
                                    action="candidate_complete", depth=current_depth,
                                    candidates=k, root_total=n, elapsed_ms=c_ms,
                                )
                            else:
                                timed_out = True
                                turbo_return_reason = "candidate-incomplete"
                            # Candidate Selection is the budgeted fallback for the
                            # level that did not fit; do not cascade to still deeper
                            # levels from a selective root result.
                            break
                    # Full Width said the full level does not fit and Candidate
                    # Selection is disabled/unavailable: keep last complete level.
                    if selective_depth is None and turbo_return_reason is None:
                        turbo_return_reason = "candidate-disabled-or-unavailable"
                    break

                level_start = time.monotonic()
                scored, complete = self._iteration(board, legal, current_depth, root, previous_score)
                level_ms = (time.monotonic() - level_start) * 1000.0
                partial_count = len(scored)

                if not complete:
                    timed_out = True
                    # Censored observation t/p estimates total level cost.
                    if legal and partial_count > 0:
                        fraction = partial_count / len(legal)
                        projected_total_ms = level_ms / fraction
                        self._turbo_observe_projection_error(projected_ms, projected_total_ms)
                        self._turbo_observe_ratio(last_level_ms, projected_total_ms)
                        self._turbo_emit(
                            f"⚡ TURBO cost censored depth={current_depth} observed_ms={level_ms:.1f} "
                            f"root={partial_count}/{len(legal)} projected_full_ms={projected_total_ms:.1f}",
                            action="cost_censored", depth=current_depth,
                            observed_ms=level_ms, root_completed=partial_count,
                            root_total=len(legal), projected_ms=projected_total_ms,
                        )
                    break

                previous_level_ms = last_level_ms
                self._turbo_observe_projection_error(projected_ms, level_ms)
                self._turbo_observe_ratio(previous_level_ms, level_ms)
                last_level_ms = level_ms
                completed = scored
                completed_depth = current_depth
                if scored:
                    previous_score = max(v for v, _ in scored)
                    self._after_level_complete(board, scored, current_depth, root)

                self._turbo_emit(
                    f"⚡ TURBO cost depth={current_depth} elapsed_ms={level_ms:.1f} "
                    f"growth={self._turbo_growth():.3f}",
                    action="cost_observation", depth=current_depth,
                    elapsed_ms=level_ms, growth=self._turbo_growth(),
                )

        elapsed_ms = (time.monotonic() - start) * 1000.0
        self._deadline = None

        if timed_out:
            self._emit_guardrail(
                attempted_depth=attempted_depth, completed_depth=completed_depth,
                root_completed=partial_count, root_total=len(legal), elapsed_ms=elapsed_ms,
            )

        if not completed:
            raise PlayerError("SARGON+ invariant violation: no complete depth-1 result")

        best_score = max(v for v, _ in completed)
        pool = [m for v, m in completed if v == best_score]
        move = self.rng.choice(pool)
        score_white = best_score if root == chess.WHITE else -best_score
        reported_depth = selective_depth if selective_depth is not None else completed_depth

        # v0.6.25: explicit proof of which completed level supplies the returned
        # move whenever TURBO abandons a deeper attempted level.  This is
        # telemetry only; it does not alter search, scoring, or fallback logic.
        if turbo_return_reason is not None and selective_depth is None and attempted_depth > completed_depth:
            self._turbo_emit(
                f"⚡ TURBO RETURN last-complete depth={completed_depth} attempted={attempted_depth} "
                f"reason={turbo_return_reason} bestmove={move.uci()} score_cp={int(score_white)}",
                action="return_last_complete", completed_depth=completed_depth,
                attempted_depth=attempted_depth, reason=turbo_return_reason,
                bestmove=move.uci(), score_white_cp=int(score_white),
            )

        if self.audit is not None:
            self.audit.event(
                'boost_search_metrics', schema=2, search_id=self._boost_audit_run,
                boost_mask=self.boost, turbo_mask=self.turbo,
                requested_depth=self.depth, completed_depth=completed_depth,
                attempted_depth=attempted_depth, timed_out=timed_out,
                bestmove=move.uci(), score_white_cp=int(score_white),
                root_fen=board.fen(), nodes=self.nodes, elapsed_ms=elapsed_ms,
                nps=round(1000*self.nodes/elapsed_ms, 2) if elapsed_ms>0 else None,
                counters=dict(self._boost_audit_counters),
                turbo_counters=dict(self._turbo_audit_counters),
                coverage=self._audit_summary(),
            )
            self.audit.event(
                "sargon_iterative_result", target_depth=self.depth,
                completed_depth=completed_depth, attempted_depth=attempted_depth,
                selective_depth=selective_depth, selective_count=selective_count,
                timed_out=timed_out, mandatory_level_overrun=budget_exhausted_by_d1,
                root_total=len(legal), nodes=self.nodes, elapsed_ms=elapsed_ms,
                bestmove=move.uci(), score_white_cp=int(score_white), turbo=self.turbo,
            )
        return MoveChoice(move, int(score_white), reported_depth, self.nodes, elapsed_ms, self.name)

