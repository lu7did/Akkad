"""Experimental Sargon-style 10x12 mailbox v0.1.19, independent of production ChessCore.
Square public notation is a1=0..h8=63; mailbox off-board sentinel=255.
No persistent 64-square board: Grumpy receives a lazy, read-only 64-square view.
"""
from chesscore import Board as ReferenceBoard, START

OFF=255
IDX=tuple(21+(sq//8)*10+(sq%8) for sq in range(64))
KN=(-21,-19,-12,-8,8,12,19,21)
BI=(-11,-9,9,11)
RO=(-10,-1,1,10)
KI=BI+RO

class SquaresView:
 def __init__(self,owner):self.owner=owner
 def __len__(self):return 64
 def __getitem__(self,k):
  if isinstance(k,slice):return [self[i] for i in range(*k.indices(64))]
  return self.owner.at64(k)
 def __iter__(self):
  b=self.owner.cells
  for i in IDX:yield b[i]-6

class Board120:
 def __init__(self,fen=START):
  # Reference parser used solely at construction; not used in generation/search.
  ref=ReferenceBoard(fen)
  self.cells=bytearray([OFF]*120)
  for i in IDX:self.cells[i]=6
  for sq,i in enumerate(IDX):self.cells[i]=ref.squares[sq]+6
  self.squares=SquaresView(self)
  self.turn=ref.turn;self.castle=ref.castle[:];self.ep=ref.ep
  self.halfmove=ref.halfmove;self.fullmove=ref.fullmove
  self._undos=[]
  self._history=[self.position_key()]
  self.gc_low_watermark=24576
  self.gc_critical_watermark=8192
  self.gc_check_every=8
  self.gc_checks=0;self.gc_runs=0;self.gc_ms=0;self.gc_critical=0;self.gc_min_free=0
 def at64(self,sq):return self.cells[IDX[sq]]-6
 @staticmethod
 def notation(move):return ReferenceBoard.notation(move)
 def in_check(self,color=None):
  color=self.turn if color is None else color
  king=6+6*color
  try:sq=self.cells.index(king)
  except ValueError:return True
  return self.attacked(sq,-color)
 def attacked(self,sq,by):
  b=self.cells
  # Pawn origins relative to target, using mailbox offsets.
  for off in (-9*by,-11*by):
   if b[sq+off]==6+by:return True
  for off in KN:
   if b[sq+off]==6+2*by:return True
  for off in KI:
   if b[sq+off]==6+6*by:return True
  for offsets,kinds in ((BI,(3,5)),(RO,(4,5))):
   for d in offsets:
    p=sq+d
    while b[p]!=OFF:
     v=b[p]-6
     if v:
      if v*by in kinds:return True
      break
     p+=d
  return False
 def pseudo(self):
  b=self.cells;side=self.turn
  for src64,src in enumerate(IDX):
   piece=b[src]-6
   if piece*side<=0:continue
   typ=abs(piece);y=src64//8;x=src64%8
   if typ==1:
    dest=src+10*side
    if b[dest]==6:
     dst64=src64+8*side
     for prom in ((5,4,3,2) if dst64//8 in (0,7) else (0,)):yield(src64,dst64,prom)
     if y==(1 if side==1 else 6) and b[src+20*side]==6:yield(src64,src64+16*side,0)
    for dx in (-1,1):
     if not 0<=x+dx<8:continue
     dst64=src64+8*side+dx;target=b[src+10*side+dx]
     if (target!=OFF and (target-6)*side<0 and abs(target-6)!=6) or dst64==self.ep:
      for prom in ((5,4,3,2) if dst64//8 in (0,7) else (0,)):yield(src64,dst64,prom)
   elif typ==2 or typ==6:
    for d in KN if typ==2 else KI:
     dest=src+d;p=b[dest]
     if p!=OFF and (p-6)*side<=0 and abs(p-6)!=6:
      # Mailbox index to 64-square index is arithmetic, no search.
      dst=((dest//10)-2)*8+(dest%10)-1
      yield(src64,dst,0)
    if typ==6 and not self.in_check(side):
     if side==1 and src64==4:
      if self.castle[0] and b[IDX[7]]==10 and b[IDX[5]]==6 and b[IDX[6]]==6 and not self.attacked(IDX[5],-side) and not self.attacked(IDX[6],-side):yield(4,6,0)
      if self.castle[1] and b[IDX[0]]==10 and b[IDX[1]]==6 and b[IDX[2]]==6 and b[IDX[3]]==6 and not self.attacked(IDX[3],-side) and not self.attacked(IDX[2],-side):yield(4,2,0)
     elif side==-1 and src64==60:
      if self.castle[2] and b[IDX[63]]==2 and b[IDX[61]]==6 and b[IDX[62]]==6 and not self.attacked(IDX[61],-side) and not self.attacked(IDX[62],-side):yield(60,62,0)
      if self.castle[3] and b[IDX[56]]==2 and b[IDX[57]]==6 and b[IDX[58]]==6 and b[IDX[59]]==6 and not self.attacked(IDX[59],-side) and not self.attacked(IDX[58],-side):yield(60,58,0)
   else:
    dirs=BI if typ==3 else RO if typ==4 else KI
    for d in dirs:
     dest=src+d
     while b[dest]!=OFF:
      p=b[dest]-6
      if p*side>0 or abs(p)==6:break
      dst=((dest//10)-2)*8+(dest%10)-1
      yield(src64,dst,0)
      if p:break
      dest+=d
 def push(self,m):
  fr,to,prom=m;a=IDX[fr];z=IDX[to];b=self.cells;side=self.turn
  v=b[a]-6;capt=b[z]-6;old_ep=self.ep
  if v*side<=0:raise ValueError('invalid source')
  # Constant number of touched cells; do NOT clone entire board.
  changes=[(a,b[a]),(z,b[z])]
  if abs(v)==1 and to==old_ep and not capt:
   cap=IDX[to-8*side];capt=b[cap]-6;changes.append((cap,b[cap]));b[cap]=6
  if abs(v)==6 and abs(to-fr)==2:
   rf,rt=(7,5) if to==6 else (0,3) if to==2 else (63,61) if to==62 else (56,59)
   ra,rz=IDX[rf],IDX[rt];changes.extend(((ra,b[ra]),(rz,b[rz])));b[rz]=b[ra];b[ra]=6
  old=(changes,self.turn,self.castle[:],self.ep,self.halfmove,self.fullmove,len(self._history))
  self._undos.append(old)
  b[a]=6;b[z]=6+side*prom if prom else 6+v
  if v==6:self.castle[0]=self.castle[1]=False
  if v==-6:self.castle[2]=self.castle[3]=False
  for sq,k in ((7,0),(0,1),(63,2),(56,3)):
   if fr==sq or to==sq:self.castle[k]=False
  self.ep=(fr+to)//2 if abs(v)==1 and abs(to-fr)==16 else -1
  self.halfmove=0 if abs(v)==1 or capt else self.halfmove+1
  if side==-1:self.fullmove+=1
  self.turn=-side
  self._history.append(self.position_key())
 def pop(self):
  changes,self.turn,self.castle,self.ep,self.halfmove,self.fullmove,nh=self._undos.pop()
  for sq,prior in changes:self.cells[sq]=prior
  del self._history[nh:]
 def configure_gc(self,low=24576,critical=8192,check_every=8):
  if low<critical or critical<0 or check_every<1:raise ValueError('invalid GC thresholds')
  self.gc_low_watermark=low
  self.gc_critical_watermark=critical
  self.gc_check_every=check_every
 def reset_gc_stats(self):
  self.gc_checks=0;self.gc_runs=0;self.gc_ms=0;self.gc_critical=0;self.gc_min_free=0
 def _gc_safepoint(self):
  # Called only AFTER restoring the board from a speculative move.
  import gc
  import time
  if not hasattr(gc,"mem_free"):return
  free=gc.mem_free()
  self.gc_checks+=1
  if self.gc_min_free==0 or free<self.gc_min_free:self.gc_min_free=free
  if free<self.gc_low_watermark:
   t=time.ticks_ms()
   gc.collect()
   self.gc_ms+=time.ticks_diff(time.ticks_ms(),t)
   self.gc_runs+=1
   if gc.mem_free()<self.gc_critical_watermark:self.gc_critical+=1
 def legal(self):
  # Stream pseudolegal candidates; do not allocate a second candidate list.
  # Only the returned legal list is retained, to preserve the API contract.
  result=[];side=self.turn;scanned=0
  for m in self.pseudo():
   self.push(m)
   try:safe=not self.in_check(side)
   finally:self.pop()
   if safe:result.append(m)
   scanned+=1
   # GC is managed exclusively by Engine at coarse-grained safe points.
  return result
 def parse(self,uci):
  m=ReferenceBoard.notation
  for move in self.legal():
   if m(move)==uci:return move
  raise ValueError('illegal move '+uci)
 def uci_push(self,uci):self.push(self.parse(uci))
 def is_capture(self,m):
  fr,to,_=m
  return self.at64(to)!=0 or (abs(self.at64(fr))==1 and to==self.ep and fr%8!=to%8)

 # Compatibility API for alpha-beta and full UCI game history.
 def position_key(self):
  # Repetition identity uses side, castling and legal en-passant only.
  ep=self.ep
  if ep>=0:
   valid=False;side=self.turn
   for dx in (-1,1):
    fr=ep-8*side+dx
    if 0<=fr<64 and abs(fr%8-ep%8)==1 and self.at64(fr)==side:
     a=IDX[fr];z=IDX[ep];cap=IDX[ep-8*side];b=self.cells
     va,vz,vc=b[a],b[z],b[cap]
     b[a]=6;b[z]=6+side;b[cap]=6
     try:safe=not self.in_check(side)
     finally:b[a],b[z],b[cap]=va,vz,vc
     if safe:valid=True;break
   if not valid:ep=-1
  return (bytes(self.cells[i] for i in IDX),self.turn,tuple(self.castle),ep)
 def repetition_count(self):return self._history.count(self.position_key())
 def is_fivefold(self):return self.repetition_count()>=5
 def insufficient_material(self):
  pieces=[(abs(self.at64(sq)),sq) for sq in range(64) if self.at64(sq) and abs(self.at64(sq))!=6]
  if not pieces:return True
  if any(kind in (1,4,5) for kind,_ in pieces):return False
  if len(pieces)==1 and pieces[0][0] in (2,3):return True
  if all(kind==3 for kind,_ in pieces):return len(set(((sq//8+sq%8)&1) for _,sq in pieces))==1
  return False
 def outcome(self,claim_draw=False):
  moves=self.legal()
  if not moves:return ('checkmate',-self.turn) if self.in_check() else ('stalemate',0)
  if self.insufficient_material():return ('insufficient_material',0)
  if self.is_fivefold():return ('fivefold_repetition',0)
  if self.halfmove>=150:return ('seventyfive_moves',0)
  if claim_draw and self.repetition_count()>=3:return ('threefold_claim',0)
  return None
 def is_game_over(self,claim_draw=False):return self.outcome(claim_draw) is not None
