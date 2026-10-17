"""Small independent rules engine. Square a1=0; piece signs denote side."""
START='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
PIECES=' PNBRQK'; KNIGHT=((1,2),(2,1),(-1,2),(-2,1),(1,-2),(2,-1),(-1,-2),(-2,-1))
KING=((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))
DIAG=((-1,-1),(-1,1),(1,-1),(1,1)); ORTH=((-1,0),(1,0),(0,-1),(0,1))
class Board:
 def __init__(self,fen=START):self.set_fen(fen)
 def set_fen(self,fen):
  parts=fen.split()
  if len(parts)<4:raise ValueError('FEN incomplete')
  self.squares=[0]*64; rows=parts[0].split('/')
  if len(rows)!=8:raise ValueError('FEN ranks')
  for rank,row in enumerate(rows):
   file=0
   for ch in row:
    if ch.isdigit():file+=int(ch);continue
    if ch.upper() not in 'PNBRQK' or file>=8:raise ValueError('FEN piece')
    self.squares[(7-rank)*8+file]=(1 if ch.isupper() else -1)*' PNBRQK'.index(ch.upper());file+=1
   if file!=8:raise ValueError('FEN rank size')
  if self.squares.count(6)!=1 or self.squares.count(-6)!=1:raise ValueError('FEN kings')
  if parts[1] not in ('w','b'):raise ValueError('FEN turn')
  self.turn=1 if parts[1]=='w' else -1
  self.castle=[c in parts[2] for c in 'KQkq']; ep=parts[3]
  if ep!='-' and (len(ep)!=2 or ep[0] not in 'abcdefgh' or ep[1] not in '36'):raise ValueError('FEN ep')
  self.ep=-1 if ep=='-' else (int(ep[1])-1)*8+ord(ep[0])-97
  self.halfmove=int(parts[4]) if len(parts)>4 else 0
  self.fullmove=int(parts[5]) if len(parts)>5 else 1
  if self.halfmove<0 or self.fullmove<1:raise ValueError('FEN clocks')
 def clone(self):
  b=Board.__new__(Board);b.squares=self.squares[:];b.turn=self.turn;b.castle=self.castle[:];b.ep=self.ep;b.halfmove=self.halfmove;b.fullmove=self.fullmove;return b
 def fen_key(self):return (tuple(self.squares),self.turn,tuple(self.castle),self.ep)
 def attacks(self,target,by):
  s=self.squares;x=target%8;y=target//8
  for dx in (-1,1):
   fx=x+dx;fy=y-by
   if 0<=fx<8 and 0<=fy<8 and s[fy*8+fx]==by:return True
  for dx,dy in KNIGHT:
   fx=x+dx;fy=y+dy
   if 0<=fx<8 and 0<=fy<8 and s[fy*8+fx]==by*2:return True
  for dx,dy in KING:
   fx=x+dx;fy=y+dy
   if 0<=fx<8 and 0<=fy<8 and s[fy*8+fx]==by*6:return True
  for directions,types in ((DIAG,(3,5)),(ORTH,(4,5))):
   for dx,dy in directions:
    fx=x+dx;fy=y+dy
    while 0<=fx<8 and 0<=fy<8:
     p=s[fy*8+fx]
     if p:
      if p*by in types:return True
      break
     fx+=dx;fy+=dy
  return False
 def in_check(self,color=None):
  color=self.turn if color is None else color
  try:k=self.squares.index(6*color)
  except ValueError:return True
  return self.attacks(k,-color)
 def pseudo(self):
  s=self.squares;side=self.turn
  for sq,p in enumerate(s):
   if p*side<=0:continue
   kind=abs(p);x=sq%8;y=sq//8
   if kind==1:
    fy=y+side
    if 0<=fy<8:
     dest=fy*8+x
     if not s[dest]:
      for prom in ((5,4,3,2) if fy in (0,7) else (0,)):yield (sq,dest,prom)
      if y==(1 if side==1 else 6) and not s[(y+2*side)*8+x]:yield(sq,(y+2*side)*8+x,0)
     for dx in (-1,1):
      nx=x+dx
      if 0<=nx<8:
       to=fy*8+nx
       if (s[to]*side<0 and abs(s[to])!=6) or to==self.ep:
        for prom in ((5,4,3,2) if fy in (0,7) else (0,)):yield(sq,to,prom)
   elif kind==2:
    for dx,dy in KNIGHT:
     nx=x+dx;ny=y+dy
     if 0<=nx<8 and 0<=ny<8 and s[ny*8+nx]*side<=0 and abs(s[ny*8+nx])!=6:yield(sq,ny*8+nx,0)
   elif kind==6:
    for dx,dy in KING:
     nx=x+dx;ny=y+dy
     if 0<=nx<8 and 0<=ny<8 and s[ny*8+nx]*side<=0 and abs(s[ny*8+nx])!=6:yield(sq,ny*8+nx,0)
    if not self.in_check(side):
     if side==1 and sq==4:
      if self.castle[0] and s[7]==4 and not(s[5] or s[6]) and not self.attacks(5,-side) and not self.attacks(6,-side):yield(4,6,0)
      if self.castle[1] and s[0]==4 and not(s[1] or s[2] or s[3]) and not self.attacks(3,-side) and not self.attacks(2,-side):yield(4,2,0)
     if side==-1 and sq==60:
      if self.castle[2] and s[63]==-4 and not(s[61] or s[62]) and not self.attacks(61,-side) and not self.attacks(62,-side):yield(60,62,0)
      if self.castle[3] and s[56]==-4 and not(s[57] or s[58] or s[59]) and not self.attacks(59,-side) and not self.attacks(58,-side):yield(60,58,0)
   else:
    directions=(DIAG if kind==3 else ORTH if kind==4 else DIAG+ORTH)
    for dx,dy in directions:
     nx=x+dx;ny=y+dy
     while 0<=nx<8 and 0<=ny<8:
      to=ny*8+nx;q=s[to]
      if q*side>0 or abs(q)==6:break
      yield(sq,to,0)
      if q:break
      nx+=dx;ny+=dy
 def apply(self,move):
  fr,to,prom=move;s=self.squares;v=s[fr];capt=s[to];old_ep=self.ep
  if not v or v*self.turn<=0:raise ValueError('bad move')
  s[fr]=0;s[to]=self.turn*prom if prom else v
  if abs(v)==1 and to==old_ep and not capt:
   taken=to-8*self.turn;capt=s[taken];s[taken]=0
  if abs(v)==6 and abs(to-fr)==2:
   rf,rt=(7,5) if to==6 else (0,3) if to==2 else (63,61) if to==62 else (56,59)
   s[rt]=s[rf];s[rf]=0
  if v==6:self.castle[0]=self.castle[1]=False
  if v==-6:self.castle[2]=self.castle[3]=False
  for sq,idx in ((7,0),(0,1),(63,2),(56,3)):
   if fr==sq or to==sq:self.castle[idx]=False
  self.ep=(fr+to)//2 if abs(v)==1 and abs(to-fr)==16 else -1
  self.halfmove=0 if abs(v)==1 or capt else self.halfmove+1
  if self.turn==-1:self.fullmove+=1
  self.turn=-self.turn
 def legal(self):
  result=[];side=self.turn
  for m in self.pseudo():
   b=self.clone();b.apply(m)
   if not b.in_check(side):result.append(m)
  return result
 def has_legal_ep(self):
  if self.ep<0:return False
  for dx in (-1,1):
   fr=self.ep-8*self.turn+dx
   if 0<=fr<64 and abs(fr%8-self.ep%8)==1 and self.squares[fr]==self.turn:
    b=self.clone();b.apply((fr,self.ep,0))
    if not b.in_check(self.turn):return True
  return False
 def parse(self,uci):
  if len(uci) not in (4,5) or uci[0] not in 'abcdefgh' or uci[2] not in 'abcdefgh' or uci[1] not in '12345678' or uci[3] not in '12345678':raise ValueError('bad UCI move')
  prom=0 if len(uci)==4 else ' PNBRQK'.index(uci[4].upper()) if uci[4] in 'qrbn' else -1
  m=((int(uci[1])-1)*8+ord(uci[0])-97,(int(uci[3])-1)*8+ord(uci[2])-97,prom)
  if m not in self.legal():raise ValueError('illegal move: '+uci)
  return m
 @staticmethod
 def notation(m):
  a,b,p=m
  return chr(97+a%8)+str(a//8+1)+chr(97+b%8)+str(b//8+1)+(' PNBRQK'[p].lower() if p else '')
