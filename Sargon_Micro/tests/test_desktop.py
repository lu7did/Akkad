import sys,os,unittest,random,struct
ROOT=os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0,os.path.join(ROOT,'device'))
from chesscore import Board,START
from nnue import NNUE
from engine import Engine
class TestChess(unittest.TestCase):
 def test_start(self):
  b=Board();self.assertEqual(len(b.legal()),20);self.assertFalse(b.in_check())
  for move in ('e2e4','e7e5','g1f3','b8c6','f1c4','g8f6','e1g1'):
   m=b.parse(move);b.apply(m)
  self.assertEqual(b.squares[6],6);self.assertEqual(b.squares[5],4)
 def test_ep(self):
  b=Board()
  for u in ['e2e4','a7a6','e4e5','d7d5']:
   b.apply(b.parse(u))
  self.assertTrue(b.has_legal_ep());b.apply(b.parse('e5d6'));self.assertEqual(b.squares[35],0)
 def test_promote(self):
  b=Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1');self.assertIn('a7a8q',[b.notation(m) for m in b.legal()])
 def test_checkmate(self):
  b=Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1');self.assertTrue(b.in_check());self.assertEqual(len(b.legal()),0)
 def test_stalemate(self):
  b=Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1');self.assertFalse(b.in_check());self.assertEqual(len(b.legal()),0)
 def test_perft(self):
  def walk(b,d):
   if d==0:return 1
   total=0
   for m in b.legal():
    c=b.clone();c.apply(m);total+=walk(c,d-1)
   return total
  self.assertEqual([walk(Board(),d) for d in (1,2,3)],[20,400,8902])
 def test_nnue_and_engine(self):
  net=NNUE(os.path.join(ROOT,'device','nnue.bin'));b=Board()
  self.assertIsInstance(net.evaluate(b),int)
  e=Engine(net);best,score,depth=e.bestmove(b,2000)
  self.assertIn(best,b.legal());self.assertIn(depth,(0,1,2));net.close()
if __name__=='__main__':unittest.main()
