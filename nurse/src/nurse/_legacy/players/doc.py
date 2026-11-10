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
#* doc.py
#* Player Doc: negamax PVS LMR quiescence heuristicas y TT
#* v0.6.162
#=================================================================================================================*
from __future__ import annotations
import time
from dataclasses import dataclass
import chess
from .base import Player
from ..types import MoveChoice

INF=1000000
MATE=30000

class _TimeOut(Exception):
    pass

@dataclass(slots=True)
class _Entry:
    key: int
    move: chess.Move | None
    depth: int
    score: int
    flag: int  # 0 upper, 1 exact, 2 lower

class DocPlayer(Player):
    """Búsqueda Doc: Negamax, PVS, LMR, TT y reglas mediante python-chess.

    Selective heuristics mimic the source, not exact C# tree parity.
    A bounded table replaces the original million-entry array.
    """
    name='DOC'

    def __init__(self,evaluator,depth=6,qdepth=8,tmax_ms=15000,telemetry=None,tt_size=8192):
        self.evaluator=evaluator
        self.depth=max(1,int(depth))
        self.qdepth=max(0,int(qdepth))
        self.tmax_ms=tmax_ms
        self.telemetry=telemetry
        self.tt_size=max(256,int(tt_size))
        self.tt=[None]*self.tt_size
        self.nodes=0
        self.kill=[None]*128
        self.history={}

    def _value(self,board):
        value=int(self.evaluator.evaluate(board))
        return value if board.turn==chess.WHITE else -value

    def _key(self,board):
        # python-chess transposition identity. Keep a legal board copy for move operations.
        return board._transposition_key()

    def _clock(self):
        if time.monotonic()>=self.deadline:
            raise _TimeOut()

    def _search(self,board,alpha,beta,depth,ply,qleft):
        self.nodes+=1
        if (self.nodes&63)==0: self._clock()
        if board.is_checkmate(): return -MATE+ply
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw() or board.is_fivefold_repetition() or board.is_seventyfive_moves(): return 0
        incheck=board.is_check()
        if incheck and depth>0: depth+=1
        qs=depth<=0
        original_alpha=alpha
        key=self._key(board)
        slot=hash(key)%self.tt_size
        entry=self.tt[slot]
        tt_move=entry.move if entry is not None and entry.key==key else None
        if not qs and entry is not None and entry.key==key and entry.depth>=depth:
            if entry.flag==1:return entry.score
            if entry.flag==2 and entry.score>=beta:return entry.score
            if entry.flag==0 and entry.score<=alpha:return entry.score
        if qs:
            stand=self._value(board)
            if not incheck:
                if stand>=beta:return stand
                alpha=max(alpha,stand)
                if qleft<=0:return alpha
            elif qleft<=0:
                # In check, cannot stand pat. Search evasions at least once.
                qleft=1
        elif not incheck and depth<=8 and self._value(board)>=beta+120*depth:
            return beta
        # python-chess legal move iterator, captures-only in quiescence unless in check.
        moves=list(board.legal_moves) if not qs or incheck else [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
        if not moves:
            return (-MATE+ply) if incheck else (alpha if qs else 0)
        def priority(m):
            if m==tt_move:return 10**9
            if board.is_capture(m):
                victim=board.piece_at(m.to_square)
                if victim is None and board.is_en_passant(m): victim=chess.Piece(chess.PAWN,not board.turn)
                return 100000000*(victim.piece_type if victim else 1)-(board.piece_type_at(m.from_square) or 0)
            if ply<len(self.kill) and self.kill[ply]==m:return 80000000
            return self.history.get((board.turn,m.from_square,m.to_square,m.promotion),0)
        moves.sort(key=priority,reverse=True)
        best=-INF
        best_move=None
        for idx,move in enumerate(moves):
            is_capture=board.is_capture(move)
            board.push(move)
            try:
                if idx==0 or qs or depth<2 or is_capture:
                    score=-self._search(board,-beta,-alpha,depth-1,ply+1,qleft-1 if qs else qleft)
                else:
                    reduction=1+idx//16
                    probe=-self._search(board,-alpha-1,-alpha,max(0,depth-1-reduction),ply+1,qleft)
                    score=probe if probe<=alpha else -self._search(board,-beta,-alpha,depth-1,ply+1,qleft)
            finally:
                board.pop()
            if score>best:
                best=score
                best_move=move
            if score>alpha:
                alpha=score
                if alpha>=beta:
                    if not is_capture:
                        if ply<len(self.kill):self.kill[ply]=move
                        k=(board.turn,move.from_square,move.to_square,move.promotion)
                        self.history[k]=self.history.get(k,0)+max(1,depth)
                    break
        if not qs:
            flag=0 if best<=original_alpha else 2 if best>=beta else 1
            self.tt[slot]=_Entry(key,best_move,depth,best,flag)
        return best

    def choose(self,board:chess.Board)->MoveChoice:
        start=time.monotonic()
        self.deadline=start+(max(1,int(self.tmax_ms or 15000))/1000)
        self.nodes=0
        self.kill=[None]*128
        self.history={}
        moves=list(board.legal_moves)
        if not moves:return MoveChoice(None,0,0,0,0.0,'DOC')
        best=moves[0]
        best_score=0
        completed=0
        # Roots searched separately to preserve last fully completed iteration.
        try:
            for depth in range(1,self.depth+1):
                candidate=None
                candidate_score=-INF
                ordered=sorted(moves,key=lambda m:m==best,reverse=True)
                alpha=-INF
                for move in ordered:
                    self._clock()
                    board.push(move)
                    try:
                        score=-self._search(board,-INF,-alpha,depth-1,1,self.qdepth)
                    finally:
                        board.pop()
                    if score>candidate_score:
                        candidate_score=score
                        candidate=move
                    alpha=max(alpha,score)
                best,best_score=candidate,candidate_score
                completed=depth
        except _TimeOut:
            pass
        score_white=best_score if board.turn==chess.WHITE else -best_score
        return MoveChoice(best,int(score_white),completed,self.nodes,(time.monotonic()-start)*1000,'DOC')
