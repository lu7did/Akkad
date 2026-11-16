import sys,types,unittest,tempfile,json,argparse
from pathlib import Path
root=Path('/mnt/data/nurse_mcts_v137/nurse')
sys.path.insert(0,str(root/'src'))
try:import chess
except ImportError:
 chess=types.ModuleType('chess');chess.__path__=[];chess.pgn=types.ModuleType('chess.pgn');sys.modules['chess']=chess;sys.modules['chess.pgn']=chess.pgn
from nurse.config import read_brain,NATIVE,EVALUATORS
from nurse._legacy.brains import PLAYER_CHOICES,EVALUATOR_CHOICES,validate,defaults
from nurse._legacy.cli_common import add_engine_args
from nurse import match
from nurse.worker import Worker
class TestMCTSPControls(unittest.TestCase):
 def test_registries_and_cli(self):
  self.assertIn('mctsp',NATIVE);self.assertIn('mctse',EVALUATORS)
  self.assertIn('mctsp',PLAYER_CHOICES);self.assertIn('mctse',EVALUATOR_CHOICES)
  ap=argparse.ArgumentParser();add_engine_args(ap)
  a=ap.parse_args(['--player','mctsp','--evaluator','mctse','--network','net.pt'])
  self.assertEqual((a.player,a.evaluator),('mctsp','mctse'))
  ap=argparse.ArgumentParser();match.add_side(ap,'a');match.add_side(ap,'b')
  a=ap.parse_args(['--a-player','mctsp','--a-evaluator','mctse','--b-player','mctsp','--b-evaluator','mctse'])
  self.assertEqual((a.a_player,a.b_evaluator),('mctsp','mctse'))
  self.assertEqual(defaults('mctsp','mctse')['evaluator'],'mctse')
 def test_read_brain_correct_and_fail_fast(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);(d/'model.pt').write_bytes(b'stub')
   v={'type':'nurse','player':'mctsp','evaluator':{'evaluator':'mctse','network':'model.pt'},'arguments':{'sims':80,'depth':6,'cpuct':1.4},'Depth':6}
   p=d/'brains.json';p.write_text(json.dumps({'brains':{'m':v}}))
   resolved=read_brain(p,'m');self.assertEqual(resolved['_player'],'mctsp');self.assertEqual(resolved['_evaluator'],'mctse');self.assertEqual(resolved['_network'],str(d/'model.pt'))
   self.assertEqual(validate({'player':'mctsp','evaluator':'mctse','network':'model.pt'})['player'],'mctsp')
   for field,value in [('evaluator',{'evaluator':'classic','network':'model.pt'}),('player','sargon'),('evaluator',{'evaluator':'mctse'}),('arguments',{'sims':0}),('arguments',{'cpuct':-1}),('arguments',{'irrelevant':2}),('evaluator',{'evaluator':'mctse','network':'model.npy'})]:
    changed=dict(v);changed[field]=value;p.write_text(json.dumps({'brains':{'m':changed}}))
    with self.subTest(field=field,value=value),self.assertRaises(ValueError):read_brain(p,'m')
 def test_worker_loads_780x16_checkpoint(self):
  import torch
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'net.pt'
   weights={'embed.weight':torch.zeros(780,16),'value.weight':torch.zeros(1,16),'from_head.weight':torch.zeros(64,16),'to_head.weight':torch.zeros(64,16)}
   torch.save({'config':{'features':780,'hidden':16,'policy':'from_to','value':'tanh'},'state_dict':weights},p)
   cfg={'_network':str(p),'_evaluator':'mctse','arguments':{'sims':12,'depth':4,'cpuct':1.4},'Depth':4,'timeout':30000,'tmax':15000}
   worker=Worker('mctsp',cfg)
   try:self.assertEqual(worker.sims,12);self.assertEqual(worker.depth,4);self.assertEqual(worker.evaluator.network,str(p))
   finally:worker.close()
if __name__=='__main__':unittest.main()
