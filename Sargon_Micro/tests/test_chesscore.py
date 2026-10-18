import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(__file__)),'device'))
from chesscore import Board

def perft(board,depth):
 if not depth:return 1
 n=0
 for m in board.legal():
  board.push(m)
  n+=perft(board,depth-1)
  board.pop()
 return n

class ChessCoreTests(unittest.TestCase):
 def test_perft_start(self):
  b=Board()
  self.assertEqual([perft(b,n) for n in (1,2,3)],[20,400,8902])
  self.assertEqual(len(b.legal()),20)
 def test_make_undo(self):
  b=Board();old=b.position_key()
  for u in ('e2e4','e7e5','g1f3','b8c6'):
   b.uci_push(u)
  for i in range(4):b.pop()
  self.assertEqual(b.position_key(),old)
  self.assertEqual(b.halfmove,0)
 def test_castle(self):
  b=Board('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
  self.assertIn('e1g1',[b.notation(m) for m in b.legal()])
  self.assertIn('e1c1',[b.notation(m) for m in b.legal()])
  b.uci_push('e1g1');self.assertEqual(b.squares[5],4);b.pop();self.assertEqual(b.squares[7],4)
 def test_ep(self):
  b=Board()
  for u in ('e2e4','a7a6','e4e5','d7d5'):b.uci_push(u)
  self.assertEqual(b.position_key()[3],43)
  b.uci_push('e5d6');self.assertEqual(b.squares[35],0)
  b.pop();self.assertEqual(b.squares[35],-1)
 def test_promotion(self):
  b=Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
  self.assertEqual(sorted(b.notation(m) for m in b.legal() if m[0]==48),['a7a8b','a7a8n','a7a8q','a7a8r'])
 def test_terminals(self):
  self.assertEqual(Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1').outcome(),('checkmate',1))
  self.assertEqual(Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1').outcome(),('stalemate',0))
  self.assertEqual(Board('7k/8/8/8/8/8/8/K7 w - - 0 1').outcome(),('insufficient_material',0))
 def test_repetition(self):
  b=Board()
  cycle=('g1f3','g8f6','f3g1','f6g8')
  for u in cycle:b.uci_push(u)
  self.assertEqual(b.repetition_count(),2)
  self.assertFalse(b.is_game_over())
  for u in cycle:b.uci_push(u)
  self.assertTrue(b.is_game_over(True))
  self.assertFalse(b.is_game_over(False))
 def test_75_move(self):
  b=Board('7k/8/8/8/8/8/2R5/K7 w - - 150 80')
  self.assertEqual(b.outcome(),('seventyfive_moves',0))
 def test_fifty_claim(self):
  b=Board('7k/8/8/8/8/8/2R5/K7 w - - 100 80')
  self.assertFalse(b.is_game_over())
  self.assertTrue(b.is_game_over(True))
 def test_bad_fen(self):
  for fen in ('8/8/8/8/8/8/8/8 w - - 0 1','not-fen'):
   with self.assertRaises(ValueError):Board(fen)

if __name__=='__main__':unittest.main()

class AdditionalPerft(unittest.TestCase):
 def test_tactical_reference(self):
  b=Board('8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1')
  self.assertEqual([perft(b,d) for d in (1,2,3)],[14,191,2812])
