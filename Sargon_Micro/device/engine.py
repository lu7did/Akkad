"""Single fixed Sargon-like alpha-beta player, depth 2 / qdepth 2, no boost.
Turbo 0x01 here means budget-aware iterative full-width; no candidate pruning.
"""
import time
if hasattr(time,"ticks_ms"):
 ticks=time.ticks_ms
 diff=time.ticks_diff
else:
 ticks=lambda: int(time.monotonic()*1000)
 diff=lambda a,b:a-b
from chesscore import Board
INF=2000000; MATE=1000000
class StopSearch(Exception):pass
class Engine:
 def __init__(self,network):self.net=network;self.nodes=0;self.deadline=None;self.cancel=None;self.history=[]
 def timecheck(self):
  if (self.nodes&15)==0:
   if (self.cancel and self.cancel()):raise StopSearch()
   if self.deadline is not None and diff(ticks(),self.deadline)>=0:raise StopSearch()
 def score(self,b,legal=None):
  if legal is None:legal=b.legal()
  if not legal:return -MATE if b.in_check() else 0
  if b.halfmove>=100 or self.history.count(b.fen_key())>=2:return 0
  x=self.net.evaluate(b);return x*b.turn
 def order(self,b,moves):
  s=b.squares
  return sorted(moves,key=lambda m:(15 if m[2] else 0)+(10+abs(s[m[1]])-abs(s[m[0]])/10 if s[m[1]] else 0),reverse=True)
 def qsearch(self,b,depth,alpha,beta):
  self.nodes+=1;self.timecheck()
  moves=b.legal()
  if not moves:return -MATE if b.in_check() else 0
  if b.halfmove>=100:return 0
  if depth<=0:return self.net.evaluate(b)*b.turn
  check=b.in_check()
  stand=-INF if check else self.net.evaluate(b)*b.turn
  if not check:
   if stand>=beta:return stand
   if stand>alpha:alpha=stand
   # SargonCore includes checking moves in qsearch
   forcing=[]
   for m in moves:
    if b.squares[m[1]] or m[2] or (abs(b.squares[m[0]])==1 and m[1]==b.ep):forcing.append(m)
    else:
     c=b.clone();c.apply(m)
     if c.in_check():forcing.append(m)
   moves=forcing
  best=stand
  for m in self.order(b,moves):
   c=b.clone();c.apply(m)
   v=-self.qsearch(c,depth-1,-beta,-alpha)
   if v>best:best=v
   if v>alpha:alpha=v
   if alpha>=beta:break
  return best
 def search(self,b,depth,alpha,beta):
  self.nodes+=1;self.timecheck()
  moves=b.legal()
  if not moves:return -MATE if b.in_check() else 0
  if b.halfmove>=100:return 0
  if depth==0:return self.qsearch(b,2,alpha,beta)
  best=-INF
  for m in self.order(b,moves):
   c=b.clone();c.apply(m)
   v=-self.search(c,depth-1,-beta,-alpha)
   if v>best:best=v
   if v>alpha:alpha=v
   if alpha>=beta:break
  return best
 def bestmove(self,b,budget_ms=5000,cancel=None):
  legal=b.legal()
  if not legal:return None,0,0
  self.cancel=cancel;self.nodes=0;self.deadline=ticks()+max(1,budget_ms)
  fallback=legal[0];best=fallback;value=0;complete_depth=0
  # Fixed 0x01 turbo: complete full-width depth1 before attempting depth2.
  for depth in (1,2):
   try:
    top=-INF;choice=fallback;alpha=-INF
    for m in self.order(b,legal):
     self.timecheck();c=b.clone();c.apply(m)
     v=-self.search(c,depth-1,-INF,INF)
     if v>top:top=v;choice=m
    best=choice;value=top;complete_depth=depth
   except StopSearch:break
  return best,value,complete_depth
