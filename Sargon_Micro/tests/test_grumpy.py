import os,sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'device'));sys.path.insert(0,str(ROOT/'tools'))
from chesscore import Board
from grumpy import Grumpy
from engine import Engine
from convert_grumpy import convert
class TestGrumpy(unittest.TestCase):
 def test_roundtrip(self):
  with tempfile.TemporaryDirectory() as td:
   f=os.path.join(td,'model.bin');convert(ROOT/'networks/grumpy.nnx',f)
   self.assertEqual(Path(f).read_bytes(),(ROOT/'device/grumpy.bin').read_bytes())
 def test_eval(self):
  g=Grumpy(str(ROOT/'device/grumpy.bin'))
  self.assertIsInstance(g.evaluate(Board()),int)
  b=Board();b.push(b.parse('e2e4'));self.assertIsInstance(g.evaluate(b),int);b.pop()
 def test_search(self):
  g=Grumpy(str(ROOT/'device/grumpy.bin'))
  e=Engine(g);m,_,depth=e.bestmove(Board(),1500)
  self.assertIn(m,Board().legal());self.assertGreaterEqual(depth,1)
 def test_corruption(self):
  with tempfile.TemporaryDirectory() as td:
   f=os.path.join(td,'bad.bin');z=bytearray((ROOT/'device/grumpy.bin').read_bytes());z[-1]^=1;Path(f).write_bytes(z)
   with self.assertRaises(ValueError):Grumpy(f)
if __name__=='__main__':unittest.main()
