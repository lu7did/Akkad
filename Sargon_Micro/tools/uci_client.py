"""Minimal TCP/UCI smoke test for a powered Pico W."""
import argparse,socket
p=argparse.ArgumentParser();p.add_argument('host');p.add_argument('--port',type=int,default=6110);a=p.parse_args()
with socket.create_connection((a.host,a.port),timeout=10) as s:
 s.settimeout(30)
 for cmd,end in [('uci','uciok'),('isready','readyok'),('position startpos\ngo movetime 1000','bestmove')]:
  print('SEND',cmd);s.sendall((cmd+'\n').encode());r=''
  while end not in r:
   x=s.recv(1024)
   if not x:raise RuntimeError('connection closed early')
   r+=x.decode(errors='replace')
  print(r.strip())
 s.sendall(b'quit\n')
