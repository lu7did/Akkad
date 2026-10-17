import os,sys,unittest,tempfile
ROOT=os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0,os.path.join(ROOT,'device'))
from nnue import NNUE,NWEIGHTS
from chesscore import Board
class ResidentTests(unittest.TestCase):
 def test_resident(self):
  net=NNUE(os.path.join(ROOT,'device','nnue.bin'))
  self.assertIsInstance(net.weights,bytearray)
  self.assertEqual(len(net.weights),NWEIGHTS)
  score=net.evaluate(Board())
  self.assertIsInstance(score,int)
  net.close()
  self.assertEqual(net.evaluate(Board()),score)
 def test_crc_rejected(self):
  with open(os.path.join(ROOT,'device','nnue.bin'),'rb') as f: raw=bytearray(f.read())
  raw[-1]^=1
  with tempfile.TemporaryDirectory() as d:
   p=os.path.join(d,'bad.bin')
   with open(p,'wb') as f:f.write(raw)
   with self.assertRaises(ValueError):NNUE(p)
if __name__=='__main__':unittest.main()
