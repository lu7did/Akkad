import os,sys,socket,threading,unittest,tempfile
ROOT=os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0,os.path.join(ROOT,'device'));sys.path.insert(0,os.path.join(ROOT,'tools'))
from main import Session,configuration
from nnue import NNUE
from engine import Engine
from make_config import make
class TestUci(unittest.TestCase):
 def test_config(self):
  with tempfile.TemporaryDirectory() as d:
   p=os.path.join(d,'config.bin');make(p,'Pico test','ssidtest','pass1234',6110)
   self.assertEqual(configuration(p),('Pico test','ssidtest','pass1234',6110))
 def test_session(self):
  a,b=socket.socketpair();net=NNUE(os.path.join(ROOT,'device','nnue.bin'))
  t=threading.Thread(target=Session(a,'Test Engine',Engine(net)).run);t.start()
  b.settimeout(5)
  def exchange(text,terminal):
   b.sendall((text+'\n').encode());data=b''
   while terminal not in data:data+=b.recv(4096)
   return data
  try:
   r=exchange('uci',b'uciok');self.assertIn(b'id name Test Engine',r)
   self.assertIn(b'readyok',exchange('isready',b'readyok'))
   exchange('position startpos moves e2e4 e7e5\ngo movetime 400',b'bestmove')
  finally:
   b.sendall(b'quit\n');b.close();t.join(5);net.close()
if __name__=='__main__':unittest.main()
