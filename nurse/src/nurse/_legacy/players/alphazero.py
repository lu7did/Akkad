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
#* alphazero.py
#* Implementa el jugador AlphaZero y la busqueda MCTS
#* v0.6.153
#=================================================================================================================*
"""AlphaZero-like PUCT search with an evaluator providing policy/value.

The neural network is never trained. MCTS statistics and NN cache remain
strictly in memory; no persistent Q, no cross-game learning, no hidden PGN IO.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math, random, time
import chess
from .base import Player, PlayerError
from ..types import MoveChoice
from ..evaluators.lc0 import LC0Evaluator, cp_from_q

@dataclass
class _Node:
    turn: bool
    prior: dict[chess.Move,float] = field(default_factory=dict)
    visits: dict[chess.Move,int] = field(default_factory=dict)
    totals: dict[chess.Move,float] = field(default_factory=dict)
    children: dict[chess.Move, '_Node'] = field(default_factory=dict)
    expanded: bool = False

    def pick(self, cpuct):
        total = sum(self.visits.values())
        root = math.sqrt(max(1,total))
        def priority(move):
            n = self.visits[move]
            q = self.totals[move] / n if n else 0.0
            return q + cpuct*self.prior[move]*root/(n+1)
        return max(self.prior, key=priority)

class AlphaZeroPlayer(Player):
    name = 'ALPHAZERO'
    def __init__(self, evaluator, *, simulations=128, cpuct=1.5, tmax_ms=15000,
                 seed=None, telemetry=None):
        if not callable(getattr(evaluator, "evaluate_pv", None)):
            raise PlayerError('player=alphazero requires evaluator with evaluate_pv(board)')
        if simulations <= 0 or cpuct <= 0:
            raise PlayerError('alphazero simulations and cpuct must be > 0')
        self.evaluator = evaluator
        self.simulations = int(simulations)
        self.cpuct = float(cpuct)
        self.tmax_ms = int(tmax_ms) if tmax_ms is not None else None
        self.random = random.Random(seed)
        self.telemetry = telemetry
        self.last_visits = {}

    def new_game(self):
        self.evaluator.new_game()
        self.last_visits = {}

    @staticmethod
    def _terminal_q(board):
        outcome=board.outcome(claim_draw=True)
        if outcome is None: return None
        if outcome.winner is None: return 0.0
        return 1.0 if outcome.winner == board.turn else -1.0

    def _expand(self, node, board):
        info=self.evaluator.evaluate_pv(board)
        if not info.policy: return info.q
        node.prior=dict(info.policy)
        node.visits={m:0 for m in node.prior}
        node.totals={m:0.0 for m in node.prior}
        node.expanded=True
        return info.q

    def _simulation(self, root, board):
        cursor = root
        path=[]
        while True:
            terminal=self._terminal_q(board)
            if terminal is not None:
                value=terminal
                break
            if not cursor.expanded:
                value=self._expand(cursor,board)
                break
            if not cursor.prior:
                value=0.0;break
            move=cursor.pick(self.cpuct)
            path.append((cursor,move))
            board.push(move)
            cursor=cursor.children.setdefault(move,_Node(board.turn))
        # value is always expressed from leaf side-to-move's perspective.
        # Flip once at every preceding ply before updating that edge.
        for parent,move in reversed(path):
            value=-value
            parent.visits[move]+=1
            parent.totals[move]+=value

    def choose(self, board):
        start=time.monotonic()
        if not any(board.legal_moves): return MoveChoice(None,0,0,0,0.0,'ALPHAZERO')
        root=_Node(board.turn)
        self._expand(root,board)
        deadline = start + self.tmax_ms/1000 if self.tmax_ms and self.tmax_ms > 0 else float('inf')
        done=0
        for _ in range(self.simulations):
            if done and time.monotonic()>=deadline: break
            self._simulation(root,board.copy(stack=True))
            done+=1
        counts=root.visits
        self.last_visits={m.uci():n for m,n in counts.items()}
        if any(counts.values()):
            best=max(counts,key=lambda m:(counts[m],root.totals[m]/max(1,counts[m]),root.prior[m]))
            q=root.totals[best]/counts[best]
        else:
            best=max(root.prior,key=root.prior.get)
            q=0.0
        cp=cp_from_q(q)
        if board.turn==chess.BLACK:cp=-cp
        elapsed=(time.monotonic()-start)*1000
        if self.telemetry:
            self.telemetry(f'🧠 ALPHAZERO sims={done} best={best.uci()} visits={counts[best]} q={q:+.4f} elapsed_ms={elapsed:.1f}')
        return MoveChoice(best,cp,0,done,elapsed,f'ALPHAZERO-{self.evaluator.name}')
