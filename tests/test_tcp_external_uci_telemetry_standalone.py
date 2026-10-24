import sys,types,importlib.util,queue
chess=types.ModuleType('chess')
class Move:
 def __init__(self,s):self.s=s
 @classmethod
 def from_uci(cls,s):return cls(s)
 def __eq__(self,o):return isinstance(o,Move) and self.s==o.s
chess.Move=Move;chess.Board=object;sys.modules['chess']=chess
for name in ('pkg','pkg.players'):
 m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m
base=types.ModuleType('pkg.players.base');base.Player=type('Player',(),{});base.PlayerError=type('PlayerError',(Exception,),{});sys.modules[base.__name__]=base
types_mod=types.ModuleType('pkg.types');types_mod.MATE_CP=100000
class MoveChoice:
 def __init__(self,*a):self.move,self.score_cp,self.depth,self.nodes,self.elapsed_ms,self.source=a
types_mod.MoveChoice=MoveChoice;sys.modules[types_mod.__name__]=types_mod
spec=importlib.util.spec_from_file_location('pkg.players.tcp_external','/mnt/data/workfix/tcp_external.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=m.TCPExternalUCIPlayer.__new__(m.TCPExternalUCIPlayer)
p.q=queue.Queue();p.timeout_ms=1000;p.name='EXTERNAL';p._send=lambda cmd:None
class Board:
 def fen(self):return 'test'
 legal_moves=[Move('d2d4')]
 def is_game_over(self,claim_draw):return False
for line in ['info nodes 50 time 9961','bestmove d2d4']:p.q.put(line)
r=p.choose(Board());assert (r.nodes,r.depth,r.score_cp,r.move.s)==(50,0,0,'d2d4')
for line in ['info depth 12 score cp -37 nodes 420 time 99','bestmove d2d4']:p.q.put(line)
r=p.choose(Board());assert (r.nodes,r.depth,r.score_cp)==(420,12,-37)
p.q.put('bestmove d2d4');r=p.choose(Board());assert r.nodes==0, 'no stale metrics'
print('PASS: picoAlpha info, standard UCI info, no stale data')
