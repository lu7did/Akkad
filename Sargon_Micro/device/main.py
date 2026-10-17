"""Pico W TCP UCI server; WiFi reconnects, one owner, guarded parsing."""
import struct,gc,time
try: import select
except ImportError: select=None
try: import network, socket
except ImportError: import socket;network=None
from chesscore import Board,START
from nnue import NNUE
from engine import Engine
from statusled import StatusLED
CONFIG_FMT='<8s32s32s64sH'
def checksum(buf, a=1, b=0):
 for x in buf:
  a=(a+x)%65521;b=(b+a)%65521
 return (b<<16)|a
def configuration(path='config.bin'):
 with open(path,'rb') as f:raw=f.read()
 if len(raw)!=struct.calcsize(CONFIG_FMT)+4:raise ValueError('config size')
 body=raw[:-4];crc=struct.unpack('<I',raw[-4:])[0]
 if checksum(body)!=crc:raise ValueError('config CRC')
 magic,n,ssid,pw,port=struct.unpack(CONFIG_FMT,body)
 if magic!=b'SPCFG101':raise ValueError('config format')
 decode=lambda v:v.split(b'\0',1)[0].decode('utf8')
 return decode(n),decode(ssid),decode(pw),port
try:
 import sys
 def log(s):
  try: print(s)
  except Exception:pass
except Exception:
 def log(s):pass
class Session:
 def __init__(self,client,name,engine,led=None):
  self.client=client;self.name=name;self.engine=engine;self.led=led;self.board=Board();self.hist=[];self.buffer=b'';self.active=True;self.stopped=False
 def send(self,line):
  log('UCI >> '+line)
  self.client.sendall((line+'\n').encode())
 def cancel_search(self):
  if select is None:return False
  try:
   readable,_,_=select.select([self.client],[],[],0)
   if not readable:return False
   data=self.client.recv(256)
   if not data:
    self.active=False;return True
   # stop and quit are actionable while search is running; other commands
   # remain buffered for dispatch after bestmove.
   self.buffer+=data
   if len(self.buffer)>2048:self.active=False;return True
   pending=[]
   while b'\n' in self.buffer:
    raw,self.buffer=self.buffer.split(b'\n',1)
    cmd=raw.strip().decode('utf8','ignore')
    if cmd=='stop':self.stopped=True;log('UCI << stop')
    elif cmd=='quit':self.active=False;log('UCI << quit')
    else:pending.append(raw+b'\n')
   self.buffer=b''.join(pending)+self.buffer
   return self.stopped or not self.active
  except OSError:
   self.active=False;return True
 def dispatch(self,line):
  log('UCI << '+line);words=line.split()
  if not words:return
  cmd=words[0]
  if cmd=='uci':
   self.send('id name '+self.name);self.send('id author Dr. Pedro E. Colla');self.send('uciok')
  elif cmd=='isready':self.send('readyok')
  elif cmd=='ucinewgame':self.board=Board();self.hist=[];gc.collect()
  elif cmd=='position':
   if len(words)<2:return
   try:
    if words[1]=='startpos':b=Board();at=2
    elif words[1]=='fen':
     k=words.index('moves') if 'moves' in words else len(words)
     b=Board(' '.join(words[2:k]));at=k
    else:raise ValueError('position command')
    h=[]
    if at<len(words) and words[at]=='moves':
     for w in words[at+1:]:
      h.append(b.fen_key());b.apply(b.parse(w))
    self.board=b;self.hist=h[-120:]
   except Exception as exc:log('position rejected: '+str(exc))
  elif cmd=='go':
   try:
    wtime=btime=None;movetime=None
    for i,v in enumerate(words):
     if v in ('wtime','btime','movetime') and i+1<len(words):
      x=max(0,int(words[i+1]));
      if v=='wtime':wtime=x
      elif v=='btime':btime=x
      else:movetime=x
    remaining=wtime if self.board.turn==1 else btime
    budget=movetime if movetime is not None else min(5000,max(100,int(remaining/30))) if remaining is not None else 5000
    self.engine.history=self.hist
    self.stopped=False
    best,score,depth=self.engine.bestmove(self.board,budget_ms=budget,cancel=self.cancel_search)
    if not self.active:return
    self.send('info depth %d score cp %d nodes %d'%(depth,score,self.engine.nodes))
    self.send('bestmove '+(Board.notation(best) if best else '0000'))
   except Exception as exc:
    log('go failure: '+str(exc));self.send('bestmove 0000')
  elif cmd=='stop':pass # synchronous search; no active search while dispatching
  elif cmd=='quit':self.active=False
 def run(self):
  try:
   self.client.settimeout(1.0)
   while self.active:
    try:packet=self.client.recv(256)
    except OSError:continue
    if not packet:break
    self.buffer+=packet
    if len(self.buffer)>2048:log('UCI buffer overflow');break
    while b'\n' in self.buffer:
     raw,self.buffer=self.buffer.split(b'\n',1)
     try:line=raw.strip().decode('utf8')
     except Exception:continue
     self.dispatch(line)
     if not self.active:break
  finally:
   try:self.client.close()
   except Exception:pass
   log('TCP disconnected');
   if self.led:self.led.set('ready')
   gc.collect()
def serve(led=None):
 if led is None:led=StatusLED()
 led.set('initializing')
 name,ssid,pw,port=configuration()
 net=NNUE();engine=Engine(net)
 log('NNUE resident SRAM bytes=%d heap_before=%d heap_after=%d'%(len(net.weights),net.heap_before,net.heap_after))
 if network is None:raise RuntimeError('WiFi requires Pico W MicroPython')
 sta=network.WLAN(network.STA_IF);sta.active(True)
 while True:
  if not sta.isconnected():
   led.set('initializing')
   log('WiFi connecting '+ssid);sta.connect(ssid,pw)
   for _ in range(30):
    if sta.isconnected():break
    time.sleep(1)
   if not sta.isconnected():log('WiFi retry');time.sleep(2);continue
  server=socket.socket();
  try:
   server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
   server.bind(('0.0.0.0',port));server.listen(1);server.settimeout(3)
   log('UCI ready TCP port '+str(port)+' IP '+str(sta.ifconfig()[0]))
   led.set('ready')
   while sta.isconnected():
    try:client,addr=server.accept()
    except OSError:continue
    log('TCP connected '+str(addr))
    led.set('playing')
    Session(client,name,engine,led).run()
  except Exception as exc:
   led.set('initializing')
   log('TCP restart: '+str(exc));time.sleep(1)
  finally:
   try:server.close()
   except Exception:pass
   gc.collect()
def boot():
 led=None
 try:
  led=StatusLED()
  serve(led)
 except Exception as exc:
  log('FATAL: '+str(exc))
  if led is not None:
   try:led.set('fatal')
   except Exception as led_exc:log('LED fatal indicator unavailable: '+str(led_exc))
  while True:time.sleep(1)
if __name__=='__main__':boot()
