import sys,tempfile,pathlib,types
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import torch
from nurse import mcts_nnue
from nurse.mcts_nnue import TinyEvaluator,Node,select
weights={'W_INPUT':torch.zeros(780,16,dtype=torch.int8),'W_VALUE':torch.zeros(1,16,dtype=torch.int8),
         'W_FROM':torch.zeros(64,16,dtype=torch.int8),'W_TO':torch.zeros(64,16,dtype=torch.int8)}
with tempfile.TemporaryDirectory() as d:
 f=pathlib.Path(d)/'best.pt'
 torch.save({'format':'picoalpha-nnue-int8-v1','config':{'features':780,'hidden':16,'policy':'from_to','value':'tanh'},'weights':weights,'scales':{name:1e-3 for name in weights}},f)
 ev=TinyEvaluator(str(f));assert ev.network==str(f)
 try:TinyEvaluator(str(pathlib.Path(d)/'missing.pt'));assert False
 except ValueError:pass
root=Node(visits=10)
a=Node(prior=.9,visits=2,value_sum=-1.0);b=Node(prior=.1,visits=2,value_sum=1.0)
root.children=[a,b]
assert select(root,1.4) is a
class Move:
 def __init__(self,n):self.n=n
 def uci(self):return self.n
class FakeBoard:
 def __init__(self,ply=0):self.ply=ply;self.turn=bool(ply%2==0);self.legal_moves=[Move('e2e4'),Move('d2d4')] if ply<3 else []
 def copy(self,stack=True):return FakeBoard(self.ply)
 def push(self,move):self.ply+=1;self.turn=not self.turn;self.legal_moves=[Move('e2e4'),Move('d2d4')] if self.ply<3 else []
 def outcome(self,claim_draw=True):return None
class FakeEval:
 def evaluate(self,b,moves=None):return (.2,{move:1/len(moves) for move in moves} if moves else {})
orig=mcts_nnue.terminal_value
mcts_nnue.terminal_value=lambda b:0.0 if b.ply>=3 else None
try:
 result=mcts_nnue.search(FakeBoard(),FakeEval(),sims=9,timeout=2000,tmax=1000,depth=2)
 assert result['simulations']==9,result
 assert result['nodes']>=3 and result['depth']<=2,result
 assert result['move'] is not None,result
 result2=mcts_nnue.search(FakeBoard(),FakeEval(),sims=999999,timeout=1,tmax=1000,depth=2)
 assert result2['simulations']<999999,result2
finally:mcts_nnue.terminal_value=orig
print('PASS: model validation, PUCT sign, legal root, simulation/depth/time budgets')
