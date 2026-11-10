"""Jennings Microchess (1976) reconstruction, version 0.3.

Piece-location table, direction-driven GNM, executable JANUS/STATE passes,
STRATGY and bounded tactical TREE. Full modern legality remains python-chess.
Not a byte-exact translation of the 6502 listing; ambiguous historical exchange
semantics and coefficients are isolated so that they can be audited.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
import chess
import time
from .base import Evaluator
from ..types import MATE_CP

VALUES = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3,
          chess.ROOK:5, chess.QUEEN:9, chess.KING:0}
OFFBOARD = 0xFF
# Square index = 8 * rank + file, as in the octal board notation.
# Slots retain identity over make/unmake, unlike a 64-square occupancy array.
_START_KINDS = [chess.KING, chess.QUEEN, chess.ROOK, chess.ROOK,
                chess.BISHOP, chess.BISHOP, chess.KNIGHT, chess.KNIGHT] + [chess.PAWN]*8
_ORTH = ((1,0),(-1,0),(0,1),(0,-1))
_DIAG = ((1,1),(1,-1),(-1,1),(-1,-1))
_KNIGHT = ((1,2),(2,1),(-1,2),(-2,1),(1,-2),(2,-1),(-1,-2),(-2,-1))

class State(IntEnum):
    INITIAL=0; CANDIDATE=4; CONTINUATION=5; RESPONSE=6
    EXCHANGE_0=0xFF; EXCHANGE_1=0xFE; EXCHANGE_2=0xFD; EXCHANGE_3=0xFC
    LEGALITY=0xF9; STRATEGY=7

@dataclass(frozen=True)
class Measurements:
    mob:int=0
    maxc:int=0
    cc:int=0

@dataclass
class _Piece:
    color:bool
    kind:int
    square:int

class PieceTable:
    """Piece-indexed board; board is a legality oracle, not the source of GNM rays.

    Slots have stable identities over a search path. The 1976 slot ordering and
    capture sentinel are conceptually reconstructed, not byte-for-byte verified.
    """
    def __init__(self, board:chess.Board):
        self.pieces=[]
        for color in (chess.WHITE,chess.BLACK):
            pool={kind:[] for kind in range(1,7)}
            for sq,p in board.piece_map().items():
                if p.color==color: pool[p.piece_type].append(sq)
            for kind in _START_KINDS:
                sq=pool[kind].pop(0) if pool[kind] else OFFBOARD
                self.pieces.append(_Piece(color,kind,sq))
            # Allow promotions which replace the original historical piece mix.
            for kind in sorted(pool):
                for sq in pool[kind]: self.pieces.append(_Piece(color,kind,sq))
        self._undos=[]
        # Derived occupancy index; the piece table remains authoritative.
        self._occupancy={p.square:i for i,p in enumerate(self.pieces) if p.square!=OFFBOARD}

    def occupant(self,square):
        return self._occupancy.get(square)

    def push(self, move:chess.Move, board_before:chess.Board):
        src=self.occupant(move.from_square)
        if src is None: raise ValueError('Piece table: source is empty')
        piece=self.pieces[src]
        ep=board_before.is_en_passant(move)
        captured_square=(move.to_square + (-8 if piece.color else 8)) if ep else move.to_square
        cap=self.occupant(captured_square)
        old_kind=piece.kind
        rook_undo=None
        if board_before.is_castling(move):
            # python-chess canonical castling move uses king destination for standard chess.
            kingside=chess.square_file(move.to_square)>chess.square_file(move.from_square)
            rank=chess.square_rank(move.from_square)
            rook_from=chess.square(7 if kingside else 0,rank)
            rook_to=chess.square(5 if kingside else 3,rank)
            ridx=self.occupant(rook_from)
            if ridx is not None:
                rook_undo=(ridx,rook_from)
                self.pieces[ridx].square=rook_to
                self._occupancy.pop(rook_from,None)
                self._occupancy[rook_to]=ridx
        self._undos.append((src,move.from_square,old_kind,cap,captured_square,rook_undo))
        if cap is not None:
            self.pieces[cap].square=OFFBOARD
            self._occupancy.pop(captured_square,None)
        self._occupancy.pop(move.from_square,None)
        piece.square=move.to_square
        self._occupancy[move.to_square]=src
        if move.promotion: piece.kind=move.promotion

    def pop(self):
        src,old_sq,old_kind,cap,cap_sq,rook_undo=self._undos.pop()
        self._occupancy.pop(self.pieces[src].square,None)
        self.pieces[src].square=old_sq
        self.pieces[src].kind=old_kind
        self._occupancy[old_sq]=src
        if cap is not None:
            self.pieces[cap].square=cap_sq
            self._occupancy[cap_sq]=cap
        if rook_undo:
            ridx,rook_sq=rook_undo
            self._occupancy.pop(self.pieces[ridx].square,None)
            self.pieces[ridx].square=rook_sq
            self._occupancy[rook_sq]=ridx

    def direction_moves(self,color:bool):
        """NEWP -> NEX -> ray distance. Emit geometric destinations, no move lists."""
        for p in self.pieces:
            if p.color!=color or p.square==OFFBOARD: continue
            f,r=p.square%8,p.square//8
            if p.kind==chess.PAWN:
                step=1 if color else -1
                nr=r+step
                if 0<=nr<8:
                    target=chess.square(f,nr)
                    if self.occupant(target) is None:
                        yield p.square,target
                        if r==(1 if color else 6):
                            target2=chess.square(f,r+2*step)
                            if self.occupant(target2) is None: yield p.square,target2
                    for df in (-1,1):
                        if 0<=f+df<8:
                            target=chess.square(f+df,nr)
                            j=self.occupant(target)
                            if j is not None and self.pieces[j].color!=color:
                                yield p.square,target
                            # en passant added by legality oracle below
                continue
            if p.kind==chess.KNIGHT: dirs=_KNIGHT; maximum=1
            elif p.kind==chess.KING: dirs=_ORTH+_DIAG; maximum=1
            elif p.kind==chess.BISHOP: dirs=_DIAG; maximum=7
            elif p.kind==chess.ROOK: dirs=_ORTH; maximum=7
            else: dirs=_ORTH+_DIAG; maximum=7
            for df,dr in dirs:
                for k in range(1,maximum+1):
                    nf,nr=f+k*df,r+k*dr
                    if not(0<=nf<8 and 0<=nr<8): break
                    target=chess.square(nf,nr)
                    j=self.occupant(target)
                    if j is not None and self.pieces[j].color==color:break
                    yield p.square,target
                    if j is not None:break


def gnm(board:chess.Board,color:bool,*,captures_only=False,table:PieceTable|None=None,metrics=None,legal_moves=None):
    """Sequential direction-driven GNM, with a single legality snapshot per state.

    A caller performing multiple passes over the same state may supply an
    immutable snapshot of legal moves. Never reuse it after board.push/pop.
    """
    t0=time.perf_counter()
    table=table if table is not None else PieceTable(board)
    if metrics is not None: metrics["gnm_calls"] += 1
    try:
        if color==board.turn:
            legal_moves=tuple(board.legal_moves) if legal_moves is None else legal_moves
            allowed={}
            for move in legal_moves:
                allowed.setdefault((move.from_square,move.to_square),[]).append(move)
        else:
            allowed=None
        emitted=set()
        for src,dst in table.direction_moves(color):
            if allowed is None:
                move=chess.Move(src,dst)
                if (not captures_only or table.occupant(dst) is not None) and move not in emitted:
                    emitted.add(move)
                    if metrics is not None: metrics["gnm_moves"] += 1
                    yield move
            else:
                for move in allowed.get((src,dst),()):
                    if move in emitted or (captures_only and not board.is_capture(move)): continue
                    emitted.add(move)
                    if metrics is not None: metrics["gnm_moves"] += 1
                    yield move
        if allowed is not None:
            for move in legal_moves:
                if move not in emitted and (not captures_only or board.is_capture(move)):
                    emitted.add(move)
                    if metrics is not None: metrics["gnm_moves"] += 1
                    yield move
    finally:
        if metrics is not None: metrics["gnm_time_ms"] += (time.perf_counter()-t0)*1000.0


def measure(board:chess.Board,color:bool,table:PieceTable|None=None,metrics=None)->Measurements:
    """Measure geometric mobility, MAXC and CC from the piece-indexed table."""
    t0=time.perf_counter()
    table=table if table is not None else PieceTable(board)
    if metrics is not None: metrics["measure_calls"] += 1
    try:
        mob=0; threatened={}; mx=0
        for src,dst in table.direction_moves(color):
            if metrics is not None: metrics["gnm_moves"] += 1
            source=table.occupant(src)
            if source is None: continue
            piece=table.pieces[source]
            mob+=2 if piece.kind==chess.QUEEN else 1
            victim_idx=table.occupant(dst)
            if victim_idx is not None:
                victim=table.pieces[victim_idx]
                if victim.color!=color:
                    v=VALUES[victim.kind]
                    mx=max(mx,v)
                    threatened[dst]=v
        return Measurements(mob,mx,sum(threatened.values()))
    finally:
        if metrics is not None: metrics["measure_time_ms"] += (time.perf_counter()-t0)*1000.0


def capture_value(board:chess.Board,move:chess.Move)->int:
    if board.is_en_passant(move):return 1
    p=board.piece_at(move.to_square)
    return VALUES[p.piece_type] if p else 0


def positional_bonus(board:chess.Board,move:chess.Move,color:bool)->int:
    piece=board.piece_at(move.from_square)
    if piece is None:return 0
    home=0 if color else 7
    central=move.to_square in (chess.D4,chess.E4,chess.D5,chess.E5)
    develop=(chess.square_rank(move.from_square)==home and
             piece.piece_type in (chess.KNIGHT,chess.BISHOP))
    return 2 if central or develop else 0


def strategy_quarters(p:Measurements,w:Measurements,b:Measurements,
                      wcap:tuple[int,int,int],bcap:tuple[int,int,int])->int:
    """4 * published STRATGY. The twice-published BMAXC is combined as -12."""
    return (16*wcap[0]+5*wcap[1]+3*(w.maxc+w.cc)+w.mob+wcap[2]
            -12*b.maxc-8*b.cc-5*bcap[1]
            -(p.maxc+p.cc+p.mob+bcap[0]+bcap[2]+b.mob))

@dataclass(frozen=True)
class ExchangeResult:
    wc:tuple[int,int,int]
    bc:tuple[int,int,int]
    leaf_value:int

class Janus:
    """Executable state coordinator, rather than labels embedded in comments.

    Each state triggers GNM or TREE statistics. The stages are behavioral
    reconstructions; byte-exact transition codes await assembly verification.
    """
    def __init__(self,board:chess.Board,table:PieceTable|None=None,exchange_branch:int=3,metrics=None):
        self.board=board
        self.table=table or PieceTable(board)
        self.branch=max(1,int(exchange_branch))
        self.state=State.INITIAL
        self.trace=[]
        self.metrics=metrics

    def _set(self,state):
        self.state=state;self.trace.append(state)
        if self.metrics is not None: self.metrics["janus_states"] += 1

    def _tree(self,side:bool, max_plies:int=6)->ExchangeResult:
        """Bounded alternating legal-capture TREE; optimize entire capture line.

        At each level rank candidate exchanges by a shallow tactical score, but
        explore multiple candidates and allow early stop. This is not the 1976
        byte-exact exchange algorithm. Same-square limitation is deliberately
        absent: historical TREE's complete semantics require source audit.
        """
        board=self.board
        tree_start=time.perf_counter()
        def walk(level, sequence):
            if self.metrics is not None: self.metrics["exchange_nodes"] += 1
            if level>=max_plies or board.is_game_over(claim_draw=False):return sequence
            stage=(State.EXCHANGE_0,State.EXCHANGE_1,State.EXCHANGE_2,State.EXCHANGE_3)[min(level//2,3)]
            self._set(stage)
            legal=tuple(board.legal_moves)
            candidates=sorted(
                ((capture_value(board,m),m) for m in gnm(board,board.turn,captures_only=True,table=self.table,metrics=self.metrics,legal_moves=legal)),
                key=lambda item:(item[0],item[1].uci()),reverse=True)
            # Optional stop: not all captures should be forced.
            best=sequence
            def utility(line):
                return sum((1 if i%2==1 else -1)*v for i,v in enumerate(line))
            baseline=utility(sequence)
            best_value=baseline
            for value,move in candidates[:self.branch]:
                self.table.push(move,board);board.push(move)
                try: candidate=walk(level+1,sequence+(value,))
                finally: board.pop();self.table.pop()
                result=utility(candidate)
                # Each side makes the locally optimal adversarial decision.
                if ((level%2==0 and result<best_value) or
                    (level%2==1 and result>best_value)):
                    best,best_value=candidate,result
            return best
        # On the resulting candidate position, the opponent must move first.
        try:
            sequence=walk(0,())
        finally:
            if self.metrics is not None: self.metrics["tree_time_ms"] += (time.perf_counter()-tree_start)*1000.0
        b=[0,0,0];w=[0,0,0]
        for i,v in enumerate(sequence):
            if i%2==0:b[i//2]=v
            else:w[i//2]=v
        return ExchangeResult(tuple(w),tuple(b),sum((1 if i%2 else -1)*v for i,v in enumerate(sequence)))

    def candidate(self,move:chess.Move,*,previous:Measurements|None=None)->int:
        board=self.board; table=self.table
        if move not in board.legal_moves:raise ValueError('Illegal candidate')
        side=board.turn
        self._set(State.INITIAL)
        if previous is None:
            previous=measure(board,side,table,self.metrics)
        self._set(State.CANDIDATE)
        immediate=capture_value(board,move)
        bonus=positional_bonus(board,move,side)
        table.push(move,board);board.push(move)
        try:
            self._set(State.LEGALITY)
            if board.is_checkmate():return MATE_CP
            if board.is_stalemate():return 0
            self._set(State.CONTINUATION)
            own=measure(board,side,table,self.metrics)
            self._set(State.RESPONSE)
            rival=measure(board,not side,table,self.metrics)
            exchange=self._tree(side)
            # WCAP0 denotes the candidate's immediate capture; subsequent
            # own captures are successive WCAP1/2. No discarded WCAP slot.
            wc=(immediate,exchange.wc[0],exchange.wc[1])
            bc=exchange.bc
            self._set(State.STRATEGY)
            return 25*strategy_quarters(previous,own,rival,wc,bc)+200*bonus
        finally:
            board.pop();table.pop()


def exchanges(board:chess.Board,first_color:bool,*,branch:int=3,plies:int=6):
    """Compatibility helper, returning (BCAP,WCAP) for opponent-first search.

    Caller should pass side-to-move; no synthetic side swapping is performed.
    """
    if board.turn!=first_color:
        raise ValueError('exchange side must equal board.turn; artificial turn changes are unsafe')
    j=Janus(board,exchange_branch=branch)
    e=j._tree(not first_color,max_plies=plies)
    return e.bc,e.wc

class MicrochessEvaluator(Evaluator):
    name='MICROCHESS'
    version='0.3.2'
    def evaluate(self,board:chess.Board)->int:
        """Interchangeable white-perspective position evaluation (not STRATGY)."""
        if board.is_checkmate():return -MATE_CP if board.turn else MATE_CP
        if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves():return 0
        table=PieceTable(board)
        w=measure(board,chess.WHITE,table);b=measure(board,chess.BLACK,table)
        material=sum((1 if p.color else -1)*VALUES[p.piece_type] for p in board.piece_map().values())
        activity=w.mob-b.mob+3*(w.maxc+w.cc-b.maxc-b.cc)
        return int(100*material+25*activity)
    def evaluate_candidate(self,board:chess.Board,move:chess.Move,*,exchange_branch:int=3,metrics=None,table=None,previous=None)->int:
        return Janus(board,table=table,exchange_branch=exchange_branch,metrics=metrics).candidate(move,previous=previous)
