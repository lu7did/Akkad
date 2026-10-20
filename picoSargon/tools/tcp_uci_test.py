#!/usr/bin/env python3
import argparse,socket,time
p=argparse.ArgumentParser();p.add_argument('host');p.add_argument('--port',type=int,default=6110);p.add_argument('--timeout',type=int,default=180);a=p.parse_args()
with socket.create_connection((a.host,a.port),timeout=10) as s:
 s.settimeout(a.timeout);f=s.makefile('rb')
 def transact(command,end):
  print('>>',command,flush=True);s.sendall((command+'\n').encode())
  while True:
   line=f.readline().decode('utf8','replace').strip()
   if not line:raise SystemExit('Connection closed before '+end)
   print('<<',line,flush=True)
   if line.startswith(end):return line
 transact('uci','uciok');transact('isready','readyok');s.sendall(b'position startpos\n')
 start=time.monotonic();transact('go','bestmove ');print('Elapsed %.2fs'%(time.monotonic()-start));s.sendall(b'quit\n')
