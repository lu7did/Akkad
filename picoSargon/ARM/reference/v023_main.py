"""Sargon Micro v0.1.23 clean UCI baseline (RP2040 / RP2350 MicroPython)."""
# The Pico runs main.py at boot. Give an early serial/LED indication before imports.
try:
 from machine import Pin
 _early_led=Pin('LED',Pin.OUT)
 _early_led.on()
except Exception:
 _early_led=None
print('SARGON MICRO v0.1.23 CLEAN BOOT starting')
import struct,gc,time
try: import select
except ImportError: select=None
try: import network, socket
except ImportError: import socket;network=None
try:
 from chesscore import START
 from mailbox120 import Board120 as Board
 from grumpy import Grumpy
 from engine import Engine
 from statusled import StatusLED
except Exception as _boot_error:
 print('FATAL import: '+repr(_boot_error))
 # Blink quickly even if statusled.py cannot be imported.
 if _early_led is not None:
  while True:
   _early_led.value(1-_early_led.value())
   time.sleep_ms(100) if hasattr(time,'sleep_ms') else time.sleep(.1)
 raise
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
def heap_free():
 try:return gc.mem_free()
 except AttributeError:return -1

def mem_log(stage, collect=False):
 before=heap_free()
 if collect:gc.collect()
 after=heap_free()
 if before<0:return
 if collect:log('MEM '+stage+' free='+str(after)+'B gc_reclaimed='+str(after-before)+'B')
 else:log('MEM '+stage+' free='+str(before)+'B')

class Session:
 def __init__(self,client,name,engine,led=None):
  self.client=client;self.name=name;self.engine=engine;self.led=led;self.board=Board();self.buffer=b'';self.active=True;self.stopped=False;self.position_valid=True
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
  elif cmd=='ucinewgame':self.board=Board();self.position_valid=True;gc.collect()
  elif cmd=='position':
   self.position_valid=False
   if len(words)<2:
    log('position rejected: missing arguments');return
   try:
    if words[1]=='startpos':b=Board();at=2
    elif words[1]=='fen':
     k=words.index('moves') if 'moves' in words else len(words)
     b=Board(' '.join(words[2:k]));at=k
    else:raise ValueError('position command')
    if at<len(words) and words[at]=='moves':
     for w in words[at+1:]:
      b.push(b.parse(w))
    self.board=b
    self.position_valid=True
    gc.collect()
   except Exception as exc:log('position rejected: '+str(exc))
  elif cmd=='go':
   if not self.position_valid:
    log('UCI ERROR: go rejected because the last position command failed; closing session')
    self.active=False
    return
   fallback=None
   try:
    # Release temporary boards and move-history objects from previous UCI turns.
    # No search objects have been allocated for this go yet.
    gc.collect()
    wtime=btime=None;movetime=None
    for i,v in enumerate(words):
     if v in ('wtime','btime','movetime') and i+1<len(words):
      x=max(0,int(words[i+1]));
      if v=='wtime':wtime=x
      elif v=='btime':btime=x
      else:movetime=x
    remaining=wtime if self.board.turn==1 else btime
    # Experimental fixed-depth search: disregard clock and movetime values.
    # Stop/quit and connection loss are still honored through cancel_search.
    budget=None
    # Preserve one proven-legal fallback before starting the recursive search.
    # If the search runs out of memory, never advertise a nonterminal 0000.
    fallback_moves=self.board.legal()
    fallback=fallback_moves[0] if fallback_moves else None
    del fallback_moves
    gc.collect()
    self.stopped=False
    started=time.ticks_ms() if hasattr(time,'ticks_ms') else int(time.monotonic()*1000)
    try:
     best,score,depth=self.engine.bestmove(self.board,budget_ms=budget,cancel=self.cancel_search)
    finally:
     ended=time.ticks_ms() if hasattr(time,'ticks_ms') else int(time.monotonic()*1000)
     elapsed=time.ticks_diff(ended,started) if hasattr(time,'ticks_diff') else ended-started
     elapsed=max(0,elapsed)
     nodes=self.engine.nodes
     nps=(nodes*1000//elapsed) if elapsed else 0
     log('SEARCH elapsed_ms='+str(elapsed)+' nodes='+str(nodes)+' nps='+str(nps)+' budget_ms=unlimited max_depth=2 completed_depth='+str(getattr(self.engine,'level_stats',[])[-1][0] if getattr(self.engine,'level_stats',[]) and self.engine.level_stats[-1][1]=='complete' else 'see-uci')+' reason='+str(self.engine.abort_reason or 'depth-limit'))
     for st in self.engine.level_stats:
      log('SEARCH-LEVEL depth='+str(st[0])+' status='+str(st[1])+' elapsed_ms='+str(st[2])+' nodes='+str(st[3])+' cumulative_nodes='+str(st[4]))
     gc.collect()
    if not self.active:return
    self.send('info depth %d score cp %d nodes %d'%(depth,score,self.engine.nodes))
    self.send('bestmove '+(Board.notation(best) if best else '0000'))
   except MemoryError as exc:
    gc.collect()
    log('go failure MemoryError: '+str(exc)+' free_after_gc='+str(heap_free())+'B')
    if self.active:
     try:self.send('bestmove '+(Board.notation(fallback) if fallback else '0000'))
     except Exception as send_exc:log('go fallback send failure: '+str(send_exc))
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
   mem_log('tcp-disconnect',collect=True)
   log('TCP disconnected');
   if self.led:self.led.set('ready')
   gc.collect()
def serve(led=None):
 if led is None:led=StatusLED()
 led.set('initializing')
 mem_log('boot',collect=True)
 name,ssid,pw,port=configuration()
 net=Grumpy();engine=Engine(net)
 gc.collect();log('GRUMPY model loaded; free_heap='+str(gc.mem_free() if hasattr(gc,'mem_free') else 'desktop'))
 mem_log('grumpy-loaded')
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
   mem_log('tcp-listening',collect=True)
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
# On MicroPython main.py is the entry point. Do not depend on __name__ semantics.
boot()
