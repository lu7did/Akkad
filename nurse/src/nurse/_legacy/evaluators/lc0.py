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
#* lc0.py
#* Lc0 neural inference bridge. No lc0 search, no training, no persistent cache.
#* v0.6.153
#=================================================================================================================*
"""Lc0 neural inference bridge. No lc0 search, no training, no persistent cache.

Requires optional lczero-bindings and compatible .pb.gz neural weights.
The exposed policy is indexed by python-chess legal Moves and WDL is always
from the perspective of the side to move. An explicit legacy cp adapter is
available through evaluate(); do not use it in AlphaZero PUCT.
"""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from math import atanh, isfinite
from pathlib import Path
import os
import sys
import chess
from .base import Evaluator, EvaluatorError


@dataclass(frozen=True)
class NeuralEvaluation:
    policy: dict[chess.Move, float]
    w: float
    d: float
    l: float
    history: str
    network_id: str

    @property
    def q(self) -> float:
        return self.w - self.l


def cp_from_q(q: float, scale: float = 400.0) -> int:
    """Monotone *heuristic* WDL expected score -> centipawn adapter.
    This is not an objectively calibrated chess centipawn transformation.
    """
    if scale <= 0: raise ValueError('cp scale must be positive')
    return round(scale * 2.0 * atanh(max(-0.999, min(0.999, q))))


def wdl_from_qd(q: float, d: float) -> tuple[float, float, float]:
    # Lc0 bindings return q=W-L, d=D. Classical-value networks have D=0.
    if not (isfinite(q) and isfinite(d)) or not -1.0001 <= q <= 1.0001 or not -0.0001 <= d <= 1.0001:
        raise EvaluatorError(f'Lc0 value invalid q={q} d={d}')
    w = (1.0 - d + q) / 2.0
    l = (1.0 - d - q) / 2.0
    if min(w, d, l) < -1.e-3:
        raise EvaluatorError(f'Lc0 value internally inconsistent q={q} d={d}')
    a = [max(0., w), max(0., d), max(0., l)]
    t = sum(a)
    if t <= 0: raise EvaluatorError('Lc0 WDL zero sum')
    return tuple(x/t for x in a)


def _root_and_moves(board: chess.Board):
    moves = list(board.move_stack)
    root = board.root() if moves else board.copy(stack=False)
    return root, moves


def _normalize_moves(gs, board):
    """Map native LC0 moves to python-chess, including castling rook-square UCI.
    Require complete one-to-one bijection; never guess indices.
    """
    lc_moves = list(gs.moves())
    indices = list(gs.policy_indices())
    if len(lc_moves) != len(indices):
        raise EvaluatorError('LC0 moves/policy_indices size mismatch')
    legal = set(board.legal_moves)
    mapped = []
    for native in lc_moves:
        try:
            move = chess.Move.from_uci(str(native))
        except (ValueError, TypeError) as exc:
            raise EvaluatorError(f'LC0 invalid move {native!r}') from exc
        if move not in legal:
            options = []
            for candidate in legal:
                if not board.is_castling(candidate): continue
                king = board.king(board.turn)
                rook_square = (chess.H1 if board.turn else chess.H8) if chess.square_file(candidate.to_square) > chess.square_file(king) else (chess.A1 if board.turn else chess.A8)
                if move.from_square == king and move.to_square == rook_square: options.append(candidate)
            if len(options) == 1: move = options[0]
        if move not in legal: raise EvaluatorError(f'Lc0 returned illegal/unmapped move {native}; fen={board.fen()}')
        mapped.append(move)
    if len(set(mapped)) != len(mapped) or set(mapped) != legal:
        raise EvaluatorError(f'Lc0 legal-move coverage mismatch: lc0={len(mapped)} python-chess={len(legal)}')
    return mapped, indices


class LC0Evaluator(Evaluator):
    name = 'LC0'
    def __init__(self, network: str, *, backend: str = 'auto', backend_options: str = '',
                 history_mode: str = 'allow-incomplete', cache_size: int = 10000,
                 cp_scale: float = 400.0):
        if not network: raise EvaluatorError('--lc0-weights or --network is required for evaluator=lc0')
        p = Path(network).expanduser().resolve()
        if not p.is_file(): raise EvaluatorError(f'Lc0 weights missing: {p}')
        if history_mode not in {'strict', 'allow-incomplete'}:
            raise EvaluatorError('lc0 history mode must be strict or allow-incomplete')
        if cache_size < 0: raise EvaluatorError('lc0 cache size must be >= 0')
        # meson-python installs Windows-native dependencies (e.g. z.dll) next to
        # the lczero package rather than in its import directory. Python 3.8+
        # requires an explicit search directory for extension-module DLLs.
        # Keep the handle alive: closing it removes this directory from DLL lookup.
        self._lc0_dll_handle = None
        if os.name == 'nt':
            dll_dir = (Path(sys.prefix) / 'Lib' / 'site-packages'
                       / '.lczero_bindings.mesonpy.libs')
            if dll_dir.is_dir():
                self._lc0_dll_handle = os.add_dll_directory(str(dll_dir))
        try:
            from lczero.backends import Weights, Backend, GameState
        except ImportError as exc:
            raise EvaluatorError('lczero-bindings is not installed. Install a compatible build; CPU backends require Lc0 compiled with BLAS or ONNX-CPU.') from exc
        self._GameState = GameState
        self.weights_file = p
        # Hash the complete file once so cache never crosses model versions.
        digest = sha256()
        with p.open('rb') as file:
            for part in iter(lambda: file.read(1024*1024), b''): digest.update(part)
        self.network_id = digest.hexdigest()
        self.history_mode = history_mode
        self.cache_size = int(cache_size)
        self.cp_scale = float(cp_scale)
        self._cache = OrderedDict()
        try:
            self._weights = Weights(str(p))
            # There are several binding releases; explicit backend names must never
            # silently fall back to a different device.
            if backend == 'auto' and not backend_options:
                self._backend = Backend(weights=self._weights)
            else:
                kwargs = {'weights': self._weights}
                if backend != 'auto': kwargs['backend'] = backend
                if backend_options: kwargs['options'] = backend_options
                self._backend = Backend(**kwargs)
        except Exception as exc:
            raise EvaluatorError(f'Lc0 backend initialization failed ({backend}): {exc}') from exc

    def new_game(self):
        self._cache.clear()

    def close(self):
        self._cache.clear()
        self._backend = None

    def _gamestate(self, board):
        root, moves = _root_and_moves(board)
        # Even when moves exist after an arbitrary FEN, the pre-FEN history is
        # unknown. Never report such a path as COMPLETE.
        incomplete = root.fen() != chess.Board().fen()
        if incomplete and self.history_mode == 'strict':
            raise EvaluatorError('Lc0 complete history required but board is FEN-only')
        if moves:
            # Prefer a complete sequence constructed from the original board.
            try:
                gs = self._GameState(fen=root.fen(), moves=[m.uci() for m in moves])
            except TypeError:
                # Some released bindings expose mutable GameState.push instead.
                gs = self._GameState(fen=root.fen())
                if not hasattr(gs, 'push'):
                    raise EvaluatorError('This lczero-bindings build cannot receive complete history; choose a binding exposing GameState(moves=...) or push().')
                for move in moves: gs.push(move.uci())
            return gs, 'INCOMPLETE' if incomplete else 'COMPLETE'
        return self._GameState(fen=board.fen()), 'INCOMPLETE' if incomplete else 'COMPLETE'

    def evaluate_pv(self, board: chess.Board) -> NeuralEvaluation:
        if board.is_game_over(claim_draw=True):
            outcome = board.outcome(claim_draw=True)
            value = 0 if outcome.winner is None else (1 if outcome.winner == board.turn else -1)
            return NeuralEvaluation({}, float(value == 1), float(value == 0), float(value == -1), 'TERMINAL', self.network_id)
        root, moves = _root_and_moves(board)
        # Include exact move sequence to avoid merging histories with equal FEN.
        key = (root.fen(), tuple(m.uci() for m in moves), board.fen())
        if key in self._cache:
            value = self._cache.pop(key); self._cache[key] = value
            return value
        gs, history = self._gamestate(board)
        # Current lczero-bindings requires a sequence of Input objects, even for a single position.
        result = self._backend.evaluate([gs.as_input(self._backend)])[0]
        actions, indices = _normalize_moves(gs, board)
        scores = [float(v) for v in result.p_softmax(indices)]
        if len(scores) != len(actions) or any(not isfinite(v) or v < 0 for v in scores):
            raise EvaluatorError('Lc0 policy invalid')
        total = sum(scores)
        if total <= 0: raise EvaluatorError('Lc0 policy zero probability')
        q, d = float(result.q()), float(result.d())
        w,d,l = wdl_from_qd(q,d)
        data = NeuralEvaluation(dict(zip(actions,(v/total for v in scores))),w,d,l,history,self.network_id)
        if self.cache_size:
            self._cache[key] = data
            if len(self._cache) > self.cache_size: self._cache.popitem(last=False)
        return data

    def evaluate(self, board: chess.Board) -> int:
        """Legacy white-oriented centipawns used only by classical players."""
        ev = self.evaluate_pv(board)
        score = cp_from_q(ev.q, self.cp_scale)
        return score if board.turn == chess.WHITE else -score
