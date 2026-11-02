"""Bellman restricted policy with pure-Python alpha-beta neural fallback."""
from __future__ import annotations
import time,random
import chess
from ..types import MoveChoice,MATE_CP
from .base import Player,PlayerError

PIECE={chess.PAWN:100,chess.KNIGHT:320,chess.BISHOP:330,chess.ROOK:500,chess.QUEEN:900,chess.KING:20000}
INF=2*MATE_CP

class BellmanPlayer(Player):
    name='BELLMAN'
    def __init__(self,evaluator,depth=4,qdepth=2,tmax_ms=15000,seed=None,telemetry=None):
        if evaluator.name!='BELLMANR':raise PlayerError('Bellman requiere evaluator=bellmanR')
        if evaluator.alternate is None:raise PlayerError('Bellman requiere alternate-network de Grumpy')
        self.evaluator=evaluator;self.depth=int(depth);self.qdepth=int(qdepth);self.tmax_ms=tmax_ms
        self.nodes=0;self._tt={};self._history={};self._killers={};self._deadline=None
        self.rng=random.Random(seed);self.telemetry=telemetry
        self.last_decision = None
    def _check(self):
        if self._deadline is not None and time.perf_counter()>=self._deadline:raise TimeoutError('Bellman timeout')
    def _static(self,board):
        return int(self.evaluator.alternate.evaluate(board))*(1 if board.turn else -1)
    def _terminal(self,board,ply):
        if board.is_checkmate():return -MATE_CP+ply
        if board.is_stalemate() or board.is_insufficient_material() or board.is_fivefold_repetition() or board.is_seventyfive_moves():return 0
        return None
    def _see_simple(self,board,move):
        # Tactical material heuristic, not full recapture SEE.
        victim=board.piece_at(move.to_square)
        if victim is None and board.is_en_passant(move):value=100
        else:value=PIECE[victim.piece_type] if victim else 0
        attacker=board.piece_at(move.from_square)
        return value-(PIECE[attacker.piece_type]//10 if attacker else 0)+(PIECE[move.promotion]-100 if move.promotion else 0)
    def _see(self,board,move,limit=6):
        # Bounded exchange at the capture square, least valuable legal
        # recapturer, optional early stop. Mirrors picoSargon's SEE intent.
        if not board.is_capture(move) and not move.promotion:return 0
        target=move.to_square
        victim=board.piece_at(target)
        gain=PIECE[victim.piece_type] if victim else (100 if board.is_en_passant(move) else 0)
        if move.promotion:gain+=PIECE[move.promotion]-100
        gains=[gain];pushed=0;sign=-1
        try:
            board.push(move);pushed+=1
            for _ in range(limit):
                recaptures=[m for m in board.legal_moves if m.to_square==target and board.is_capture(m)]
                if not recaptures:break
                chosen=min(recaptures,key=lambda m:PIECE[board.piece_at(m.from_square).piece_type])
                captured=board.piece_at(target)
                value=PIECE[captured.piece_type] if captured else 100
                gains.append(gains[-1]+sign*value)
                board.push(chosen);pushed+=1;sign=-sign
        finally:
            for _ in range(pushed):board.pop()
        for i in range(len(gains)-2,-1,-1):
            gains[i]=(min if i%2==0 else max)(gains[i],gains[i+1])
        return gains[0]
    def _order(self,board,moves,ply,ttmove=None):
        def priority(m):
            if m==ttmove:return 10**9
            if board.is_capture(m) or m.promotion:return 100000+self._see_simple(board,m)+(max(-30000,self._see(board,m)) if board.is_capture(m) else 0)
            killers=self._killers.get(ply,())
            if m in killers:return 90000-killers.index(m)*1000
            return self._history.get((board.turn,m.from_square,m.to_square),0)
        return sorted(moves,key=priority,reverse=True)
    def _quiesce(self,board,alpha,beta,qleft,ply):
        self.nodes+=1
        if self.nodes%32==0:self._check()
        term=self._terminal(board,ply)
        if term is not None:return term
        checked=board.is_check()
        stand=self._static(board)
        if not checked:
            if stand>=beta:return stand
            alpha=max(alpha,stand)
            if qleft<=0:return alpha
        elif ply>64:return stand
        moves=list(board.legal_moves)
        if not moves:return -MATE_CP+ply if checked else 0
        if not checked:moves=[m for m in moves if board.is_capture(m) or m.promotion]
        for m in self._order(board,moves,ply):
            if not checked and self._see_simple(board,m)<-100:continue
            board.push(m)
            try:value=-self._quiesce(board,-beta,-alpha,max(0,qleft-1),ply+1)
            finally:board.pop()
            if value>=beta:return value
            alpha=max(alpha,value)
        return alpha
    def _search(self,board,depth,alpha,beta,ply):
        self.nodes+=1
        if self.nodes%32==0:self._check()
        terminal=self._terminal(board,ply)
        if terminal is not None:return terminal
        if depth<=0:return self._quiesce(board,alpha,beta,self.qdepth,ply)
        checked=board.is_check()
        # Bounded check extension.
        if checked and ply<12:depth+=1
        # Reverse futility pruning (non-PV, shallow).
        if depth==1 and not checked and ply>1 and abs(beta)<MATE_CP-1000:
            stand=self._static(board)
            if stand-180>=beta:return stand
        # Razoring with quiescence verification.
        if depth<=2 and not checked and ply>1 and board.halfmove_clock<80 and abs(alpha)<MATE_CP-1000:
            stand=self._static(board)
            if stand+240+160*depth<alpha:
                test=self._quiesce(board,alpha-1,alpha,self.qdepth,ply)
                if test<=alpha:return test
        # TT only in positions without near fifty move draw or repeated state.
        safe=board.halfmove_clock<80 and not board.is_repetition(2)
        key=(board.fen(en_passant="legal"),depth) if safe else None
        stored=self._tt.get(key) if key is not None else None
        if stored is not None:
            value,flag,move=stored
            if flag=='EXACT' or (flag=='LOWER' and value>=beta) or (flag=='UPPER' and value<=alpha):return value
        ttmove=stored[2] if stored else None
        orig=alpha;best=-INF;bestmove=None
        moves=self._order(board,list(board.legal_moves),ply,ttmove)
        if not moves:return -MATE_CP+ply if board.is_check() else 0
        for idx,m in enumerate(moves):
            tactical=board.is_capture(m) or bool(m.promotion)
            board.push(m)
            try:
                child_check=board.is_check()
                # Late-move reduction for late quiet candidates.
                if depth>=3 and idx>=4 and not tactical and not checked and not child_check:
                    result=-self._search(board,depth-2,-alpha-1,-alpha,ply+1)
                    if result>alpha:result=-self._search(board,depth-1,-beta,-alpha,ply+1)
                elif idx>0 and depth>=2:
                    # PVS null-window scout, followed by a full verification.
                    result=-self._search(board,depth-1,-alpha-1,-alpha,ply+1)
                    if alpha<result<beta:result=-self._search(board,depth-1,-beta,-alpha,ply+1)
                else:
                    result=-self._search(board,depth-1,-beta,-alpha,ply+1)
            finally:board.pop()
            if result>best:best=result;bestmove=m
            alpha=max(alpha,result)
            if alpha>=beta:
                if not board.is_capture(m):
                    k=self._killers.setdefault(ply,[])
                    if m in k:k.remove(m)
                    k.insert(0,m);del k[2:]
                    hk=(board.turn,m.from_square,m.to_square);self._history[hk]=self._history.get(hk,0)+depth*depth
                break
        if key is not None:
            self._tt[key]=(best,'UPPER' if best<=orig else 'LOWER' if best>=beta else 'EXACT',bestmove)
        return best
    def choose(self,board):
        start=time.perf_counter();self.last_decision=None;self.nodes=0;self._tt.clear();self._history.clear();self._killers.clear()
        self._deadline=start+self.tmax_ms/1000 if self.tmax_ms and self.tmax_ms>0 else None
        terminal=self._terminal(board,0)
        if terminal is not None:return MoveChoice(None,terminal,0,0,0,'bellman-terminal')
        result,lookup_stats=self.evaluator.lookup_with_stats(board)
        if result:
            u,score,mean,n=result;move=chess.Move.from_uci(u)
            from ..bellman_common import state_key
            record=self.evaluator.states[state_key(board)][u]
            self.last_decision={
                'method':'BELLMAN','move':u,'visits':int(n),
                'W':int(record['W']),'D':int(record['D']),'L':int(record['L']),
                'Q':round(float(mean),6),'S':round(float(score),6),
                'nmin':self.evaluator.nmin,
                'legal_examined':lookup_stats['legal_examined'],
                'hash_hits':lookup_stats['hash_hits'],
                'qualified':lookup_stats['qualified'],
                'score_unit':'wdl-expectation','cp_available':False,
            }
            # score_cp=0 is an uncalibrated protocol placeholder, NOT a conversion
            # of the WDL expectation to centipawns. UCI suppresses this field.
            elapsed=(time.perf_counter()-start)*1000
            self.last_decision['elapsed_ms']=round(elapsed,6)
            return MoveChoice(move,0,0,lookup_stats['legal_examined'],elapsed,'bellman-table')
        # Fallback uses only Python code and Grumpy. Order, TT, killers/history,
        # bounded alpha-beta and check-aware qsearch reproduce a selected subset
        # of picoSargon ideas; full C++ heuristic parity is not claimed.
        best=next(iter(board.legal_moves));bestscore=-INF;complete=0
        for d in range(1,self.depth+1):
            window=60;low=max(-INF,bestscore-window) if d>=3 and bestscore!=-INF else -INF
            high=min(INF,bestscore+window) if low!=-INF else INF
            try:
                for retry in range(24):
                    current=None;v=-INF;alpha=low;beta=high
                    for idx,move in enumerate(self._order(board,list(board.legal_moves),0,best)):
                        self._check();board.push(move)
                        try:
                            if idx>0 and d>=2:
                                x=-self._search(board,d-1,-alpha-1,-alpha,1)
                                if alpha<x<beta:x=-self._search(board,d-1,-beta,-alpha,1)
                            else:x=-self._search(board,d-1,-beta,-alpha,1)
                        finally:board.pop()
                        if x>v:v=x;current=move
                        alpha=max(alpha,x)
                    if d<3 or (low<v<high) or (low==-INF and high==INF):break
                    window*=2
                    if v<=low:low=max(-INF,v-window)
                    else:high=min(INF,v+window)
                if current is not None:best=current;bestscore=v;complete=d
            except TimeoutError:break
        if bestscore==-INF:bestscore=self._static(board)
        self.last_decision={'method':'NNUE','move':best.uci(),'depth':complete,'qdepth':self.qdepth,'nodes':self.nodes,'score_cp':int(bestscore)*(1 if board.turn else -1),'score_unit':'cp-white',
            'bellman_legal_examined':lookup_stats['legal_examined'],
            'bellman_hash_hits':lookup_stats['hash_hits']}
        return MoveChoice(best,int(bestscore)*(1 if board.turn else -1),complete,self.nodes,(time.perf_counter()-start)*1000,'bellman-fallback')
