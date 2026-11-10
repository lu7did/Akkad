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
#* zpolicy.py
#* Experimental value/P adapters for AlphaZero PUCT.
#* v0.6.153
#=================================================================================================================*
"""Experimental value/P adapters for AlphaZero PUCT.

With policy=uniform, each expansion evaluates its current position once and
uses equal priors for all legal moves (no successor evaluations).
policy=softmax retains the original successor-value experiment.
MCTS alone owns N, W and Q; no virtual visits are introduced.
"""
from __future__ import annotations

from hashlib import sha256
from math import exp, isfinite, tanh
from pathlib import Path

import chess

from .base import Evaluator, EvaluatorError
from .lc0 import NeuralEvaluation
from .classic import ClassicEvaluator
from .npz import NpzEvaluator


def _terminal_value(board: chess.Board) -> float | None:
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    if outcome.winner is None:
        return 0.0
    return 1.0 if outcome.winner == board.turn else -1.0


def _priors(centipawns: list[float], temperature: float, uniform_mix: float) -> list[float]:
    """Stable softmax; all legal moves keep strictly positive prior when mix > 0."""
    if not centipawns:
        return []
    if any(not isfinite(v) for v in centipawns):
        raise EvaluatorError('zpolicy: evaluación no finita al construir P')
    peak = max(centipawns)
    weights = [exp((v - peak) / temperature) for v in centipawns]
    total = sum(weights)
    if not isfinite(total) or total <= 0:
        raise EvaluatorError('zpolicy: política Softmax inválida')
    uniform = uniform_mix / len(weights)
    prior = [(1.0 - uniform_mix) * w / total + uniform for w in weights]
    norm = sum(prior)
    return [p / norm for p in prior]


class ValuePolicyEvaluator(Evaluator):
    """Adapter of an existing white-centipawn evaluator to AlphaZero's P/V.

    For the current position we calculate V via tanh(cp_turn/value_scale).
    With policy=uniform, legal moves receive P(s,a)=1/number_of_legal_moves.
    With policy=softmax, score each successor from the root mover's view.
    Terminal positions always use exact game result, including immediate mates.
    """
    def __init__(self, source: Evaluator, *, name: str, network_id: str,
                 temperature: float = 100.0, value_scale: float = 800.0,
                 uniform_mix: float = 0.01, policy: str = 'softmax'):
        if policy not in ('uniform', 'softmax'):
            raise EvaluatorError('--z-policy debe ser uniform o softmax')
        if not isfinite(temperature) or temperature <= 0:
            raise EvaluatorError('--z-temperature debe ser finito y > 0')
        if not isfinite(value_scale) or value_scale <= 0:
            raise EvaluatorError('--z-value-scale debe ser finito y > 0')
        if not isfinite(uniform_mix) or not 0 <= uniform_mix < 1:
            raise EvaluatorError('--z-uniform-mix debe estar entre 0 inclusive y 1 exclusivo')
        self.source = source
        self.name = name
        self.network_id = network_id
        self.temperature = float(temperature)
        self.value_scale = float(value_scale)
        self.uniform_mix = float(uniform_mix)
        self.policy = policy

    def evaluate(self, board: chess.Board) -> int:
        """Retain source's white-oriented CP API for other classical players."""
        return int(self.source.evaluate(board))

    def evaluate_pv(self, board: chess.Board) -> NeuralEvaluation:
        terminal = _terminal_value(board)
        if terminal is not None:
            return NeuralEvaluation({}, float(terminal > 0), float(terminal == 0),
                                    float(terminal < 0), 'TERMINAL', self.network_id)
        sign = 1 if board.turn == chess.WHITE else -1
        value_cp = sign * float(self.source.evaluate(board))
        if not isfinite(value_cp):
            raise EvaluatorError('zpolicy: V no finito')
        v = tanh(value_cp / self.value_scale)
        moves = list(board.legal_moves)
        if self.policy == 'uniform':
            # No successor evaluation: evaluate this leaf exactly once.
            p = 1.0 / len(moves) if moves else 0.0
            probabilities = [p] * len(moves)
        else:
            scores = []
            for move in moves:
                board.push(move)
                try:
                    successor_terminal = _terminal_value(board)
                    if successor_terminal is None:
                        # Evaluator returns white CP; retain root mover sign.
                        cp = sign * float(self.source.evaluate(board))
                    else:
                        # board.turn is now the opponent: terminal Q must flip.
                        cp = -successor_terminal * 100000.0
                    scores.append(cp)
                finally:
                    board.pop()
            probabilities = _priors(scores, self.temperature, self.uniform_mix)
        return NeuralEvaluation(dict(zip(moves, probabilities)), (1.0 + v) / 2.0,
                                0.0, (1.0 - v) / 2.0,
                                'UNIFORM' if self.policy == 'uniform' else 'SYNTHETIC',
                                self.network_id)

    def new_game(self):
        if callable(getattr(self.source, 'new_game', None)):
            self.source.new_game()

    def reload(self) -> None:
        self.source.reload()

    def close(self) -> None:
        self.source.close()


class ZClassicEvaluator(ValuePolicyEvaluator):
    def __init__(self, *, temperature=100.0, value_scale=800.0, uniform_mix=0.01,
                 policy='uniform'):
        super().__init__(ClassicEvaluator(), name='ZCLASSIC', network_id='classic-sargon-v1',
                         temperature=temperature, value_scale=value_scale,
                         uniform_mix=uniform_mix, policy=policy)


class ZNpzEvaluator(ValuePolicyEvaluator):
    def __init__(self, network: str, *, temperature=100.0, value_scale=800.0,
                 uniform_mix=0.01, policy='uniform'):
        if not network:
            raise EvaluatorError('--network es obligatorio para evaluator=znpz')
        # Never create random weights implicitly: experimental results require
        # a concrete, valid trained NPZ checkpoint.
        source = NpzEvaluator(network, require_weights=True)
        digest = sha256(Path(network).read_bytes()).hexdigest()
        super().__init__(source, name='ZNPZ', network_id=digest,
                         temperature=temperature, value_scale=value_scale,
                         uniform_mix=uniform_mix, policy=policy)
