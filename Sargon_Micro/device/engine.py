"""Doc streamlined: iterative negamax PVS/LMR, bounded TT, killers, history, qsearch."""
import time
from chesscore import Board
if hasattr(time,'ticks_ms'):
 now=time.ticks_ms;delta=time.ticks_diff
else:
 now=lambda:int(time.monotonic()*1000)
 delta=lambda a,b:a-b
INF=1000000
MATE=30000
class Timeout(Exception):pass
class Engine:
 def __init__(self,net):
  self.net=net;self.nodes=0;self.history=[]
  self.tt=[None]*128;self.kill=[None]*32;self.hist=[0]*4096
 def _clock(self):
  if (self.nodes&31)==0:
   if self.cancel and self.cancel():raise Timeout()
   if delta(now(),self.deadline)>=0:raise Timeout()
 def _score(self,b):return self.net.evaluate(b)*b.turn
 def _key(self,b):
  # Safe immutable key with correct chess state including normalized EP.
  return b.position_key()
 def _rank(self,b,m,ttmove,ply):
  if m==ttmove:return 1000000000
  fr,to,pro=m;piece=abs(b.squares[fr]);victim=abs(b.squares[to])
  if b.is_capture(m):return 100000000*max(1,victim)-piece
  if pro:return 90000000+pro*1000
  if ply<len(self.kill) and m==self.kill[ply]:return 80000000
  return self.hist[(fr*64+to)&4095]
 def _search(self,b,depth,qleft,alpha,beta,ply):
  self.nodes+=1;self._clock()
  if b.halfmove>=150 or b.is_fivefold() or b.insufficient_material():return 0
  # Repetition & 50 moves are claimable draws, treated as available neutral options.
  if b.halfmove>=100 or b.repetition_count()>=3:return 0
  incheck=b.in_check()
  legal=b.legal()
  if not legal:return (-MATE+ply) if incheck else 0
  if depth<=0:
   stand=-INF if incheck else self._score(b)
   if not incheck:
    if stand>=beta:return stand
    if stand>alpha:alpha=stand
    if qleft<=0:return alpha
    legal=[m for m in legal if b.is_capture(m) or m[2]]
   elif qleft<=0:
    # In check a legal evasion is mandatory; prevent endless check extensions.
    if ply>=20:return self._score(b)
    qleft=1
   if not legal:return alpha
   best=stand; ttmove=None
  else:
   if incheck:depth+=1
   key=self._key(b);idx=hash(key)&127;entry=self.tt[idx]
   ttmove=entry[1] if entry is not None and entry[0]==key else None
   if entry is not None and entry[0]==key and entry[2]>=depth:
    _,_,_,score,flag=entry
    if flag==1 or (flag==2 and score>=beta) or (flag==0 and score<=alpha):return score
   if not incheck and depth<=8 and self._score(b)>=beta+120*depth:return beta
   best=-INF
  ordered=sorted(legal,key=lambda m:self._rank(b,m,ttmove,ply),reverse=True)
  oldalpha=alpha;bestmove=None
  for i,m in enumerate(ordered):
   capture=b.is_capture(m)
   b.push(m)
   try:
    if depth<=0:
     v=-self._search(b,0,qleft-1,-beta,-alpha,ply+1)
    elif i==0 or depth<2 or capture:
     v=-self._search(b,depth-1,qleft,-beta,-alpha,ply+1)
    else:
     reduced=max(0,depth-2-i//16)
     probe=-self._search(b,reduced,qleft,-alpha-1,-alpha,ply+1)
     v=probe if probe<=alpha else -self._search(b,depth-1,qleft,-beta,-alpha,ply+1)
   finally:b.pop()
   if v>best:best=v;bestmove=m
   if v>alpha:alpha=v
   if alpha>=beta:
    if not capture:
     if ply<len(self.kill):self.kill[ply]=m
     k=(m[0]*64+m[1])&4095;self.hist[k]+=max(1,depth)
    break
  if depth>0:
   flag=0 if best<=oldalpha else 2 if best>=beta else 1
   self.tt[idx]=(key,bestmove,depth,best,flag)
  return best
 def bestmove(self,b,budget_ms=5000,cancel=None):
  legal=b.legal()
  if not legal:return None,0,0
  self.cancel=cancel;self.nodes=0;self.deadline=now()+max(1,int(budget_ms))
  self.kill=[None]*32;self.hist=[0]*4096
  best=legal[0];value=0;completed=0
  # Fixed full-width depth 1..4, with last-completed-depth fallback.
  for depth in (1,2,3,4):
   try:
    top=-INF;choice=best
    ordered=sorted(legal,key=lambda m:m==best,reverse=True)
    for m in ordered:
     self._clock();b.push(m)
     try:v=-self._search(b,depth-1,4,-INF,INF,1)
     finally:b.pop()
     if v>top:top=v;choice=m
    best=choice;value=top;completed=depth
   except (Timeout,MemoryError):break
  return best,value,completed
