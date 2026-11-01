"""Microchess-inspired piece-wise generation, move policy and bounded search.

Chess legality and special moves are delegated to python-chess so that the
player remains interoperable with the other Sargon-NNUE components.
"""
from __future__ import annotations
import time
import chess
from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP
from ..evaluators.microchess import VALUES, gnm, MicrochessEvaluator, State

class _Deadline(Exception): pass

class MicrochessPlayer(Player):
    name = 'MICROCHESS'

    def __init__(self, evaluator, depth=2, qdepth=0, tmax_ms=15000, telemetry=None):
        if int(depth)<1 or int(qdepth)<0: raise PlayerError('microchess: depth>=1, qdepth>=0')
        self.evaluator=evaluator
        self.depth=int(depth)
        self.qdepth=int(qdepth)
        self.tmax_ms=max(1,int(tmax_ms or 15000))
        self.telemetry=telemetry
        self.nodes=0

    @staticmethod
    def _piece_order(board):
        # Original GNM traversed piece table and rays; legal move generation
        # is centralized in python-chess to support every modern chess rule.
        moves=list(gnm(board, board.turn))
        def rank(m):
            attacker=board.piece_type_at(m.from_square)
            victim=board.piece_type_at(m.to_square)
            if board.is_en_passant(m): victim=chess.PAWN
            captured=VALUES.get(victim,0)
            square=m.to_square
            f,r=chess.square_file(square),chess.square_rank(square)
            center=(3.5-abs(3.5-f))+(3.5-abs(3.5-r))
            development=2 if attacker in (chess.KNIGHT,chess.BISHOP) and chess.square_rank(m.from_square)==(0 if board.turn else 7) else 0
            return (4*captured + 2*bool(m.promotion)+ development + .1*center,
                    -m.from_square,-m.to_square)
        return sorted(moves,key=rank,reverse=True)

    def _search(self, board, depth, qleft, alpha, beta, ply):
        self.nodes+=1
        if (self.nodes&31)==0 and time.monotonic()>self.deadline: raise _Deadline()
        if board.is_checkmate():return -MATE_CP+ply
        if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():return 0
        if depth<=0:
            stand=self.evaluator.evaluate(board) * (1 if board.turn else -1)
            if qleft<=0:return stand
            if not board.is_check():
                if stand>=beta:return stand
                alpha=max(alpha,stand)
                moves=[m for m in self._piece_order(board) if board.is_capture(m) or m.promotion]
            else:
                moves=self._piece_order(board)
            if not moves:return alpha
            for move in moves:
                board.push(move)
                try: val=-self._search(board,0,qleft-1,-beta,-alpha,ply+1)
                finally: board.pop()
                if val>=beta:return val
                alpha=max(alpha,val)
            return alpha
        for move in self._piece_order(board):
            board.push(move)
            try: val=-self._search(board,depth-1,qleft,-beta,-alpha,ply+1)
            finally: board.pop()
            if val>=beta:return val
            alpha=max(alpha,val)
        return alpha

    def choose(self, board):
        start=time.monotonic()
        self.deadline=start+self.tmax_ms/1000
        self.nodes=0
        moves=self._piece_order(board)
        if not moves:return MoveChoice(None,0,0,0,0.0,self.name)
        best=moves[0]; score=0; completed=0
        # JANUS first pass: STRATGY evaluates the candidate move rather than
        # only the resulting position. Other evaluators retain the common API.
        candidate_scores = {}
        if isinstance(self.evaluator, MicrochessEvaluator):
            for move in moves:
                if time.monotonic() >= self.deadline: break
                candidate_scores[move] = self.evaluator.evaluate_candidate(board, move)
            if candidate_scores:
                best = max(candidate_scores, key=candidate_scores.get)
                score = candidate_scores[best]
                completed = 1 if len(candidate_scores) == len(moves) else 0
        try:
            for depth in range(1,self.depth+1):
                candidate=None; value=-MATE_CP-1
                for move in sorted(moves,key=lambda m: (m!=best, -candidate_scores.get(m, 0))):
                    if time.monotonic()>self.deadline:raise _Deadline()
                    if depth == 1 and move in candidate_scores:
                        result = candidate_scores[move]
                    else:
                        board.push(move)
                        try: result=-self._search(board,depth-1,self.qdepth,-MATE_CP-1,MATE_CP+1,1)
                        finally: board.pop()
                    if result>value: value=result; candidate=move
                best,score,completed=candidate,value,depth
        except _Deadline:pass
        score_white=score if board.turn else -score
        return MoveChoice(best,int(score_white),completed,self.nodes,(time.monotonic()-start)*1000,self.name)
