#!/usr/bin/env python3
"""Hive v0.2.23 - dual-front-end UCI concentrator, persistent UCI workers.

No chess evaluation occurs here. Root scores follow side-to-move UCI convention.
All diagnostics go to stderr, never to either UCI output channel.
"""
from __future__ import annotations
import argparse
from collections import deque
import json
import datetime
import textwrap
import logging
import math
import queue
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
import cpu_affinity
import hive_beacon

try:
    import yaml
    import chess
except ImportError as exc:
    sys.stderr.write(f'Hive: dependency missing: {exc}; install requirements.txt\n')
    raise SystemExit(2)

VERSION = '0.2.23'
LOG = logging.getLogger('hive')

# All Hive observability is directed to stderr, never to either UCI wire.
# One lock protects the entire line from concurrent sessions and workers.
_TELEMETRY_LOCK = threading.RLock()
_TELEMETRY_WIDTH = 12
_TELEMETRY_VERBOSE = 1


def telemetry(symbol, name='', message='', *, verbose=False):
    # Client-facing UCI is always visible; worker wire and diagnostics are level 2.
    # Worker bestmove is represented by its consolidated summary, never twice.
    if symbol == '📮' and re.match(r'^\s*(?:info|bestmove)(?:\s|$)', str(message)):
        return
    level = 0 if symbol in ('➡️', '⬅️') else 2 if verbose or symbol in ('✉️', '📮', 'ℹ️') else 1
    if _TELEMETRY_VERBOSE < level:
        return
    stamp = datetime.datetime.now().strftime('%H:%M:%S')
    label = f'{str(name):<{_TELEMETRY_WIDTH}} ' if name else ''
    with _TELEMETRY_LOCK:
        print(f'{symbol}[{stamp}] {label}{message}'.rstrip(), file=sys.stderr, flush=True)


def report_exclusions(session, excluded, display=lambda name:name):
    for name,(kmin,reason) in excluded.items():
        weight='auto' if kmin is None else f'{kmin:.3f}'
        telemetry('⚠️',display(name),f'excluded kmin={weight} reason={reason} session={session}')


def telemetry_args(name, args, *, width=100):
    """Wrapped argv display without changing any subprocess arguments."""
    tokens = [repr(str(a)) for a in args]
    prefix_len = 12 + max(_TELEMETRY_WIDTH, len(str(name)))
    current = ''
    for token in tokens:
        part = (', ' if current else '') + token
        if current and len(current) + len(part) > max(32, width - prefix_len):
            telemetry('⚙️', name, current)
            current = token
        else:
            current += part
    if current:
        telemetry('⚙️', name, current)


MOVE = re.compile(r'^[a-h][1-8][a-h][1-8][qrbn]?$')


def tokens_info(s):
    t=s.split()
    if not t or t[0]!='info': return None
    def num(key):
        try: return int(t[t.index(key)+1])
        except (ValueError,IndexError): return None
    d=dict(depth=num('depth'), nodes=num('nodes'), nps=num('nps'), time=num('time'),
           cp=None,mate=None,bound='exact',move=None)
    if 'score' in t:
        p=t.index('score')
        if p+2 < len(t):
            try:
                if t[p+1]=='cp':d['cp']=int(t[p+2])
                if t[p+1]=='mate':d['mate']=int(t[p+2])
            except ValueError: pass
    if 'lowerbound' in t:d['bound']='lowerbound'
    if 'upperbound' in t:d['bound']='upperbound'
    if 'pv' in t:
        j=t.index('pv')+1
        if j<len(t) and MOVE.fullmatch(t[j]):d['move']=t[j]
    return d


def numeric_score(info):
    """Only for the prototype MAX_CP policy; mate takes precedence."""
    m=info.get('mate')
    if m is not None:return (100000-abs(m)) if m>0 else (-100000+abs(m))
    return info.get('cp')


def apportion_moves(weights,count):
    """Largest remainders; exact total, deterministic ties by endpoint name."""
    if count<0 or not weights or any(not math.isfinite(w) or w<0 for w in weights.values()):
        raise ValueError('invalid move allocation')
    total=math.fsum(weights.values())
    if abs(total-1)>1e-9:raise ValueError('move weights do not sum to one')
    quotas={name:count*w/total for name,w in weights.items()}
    counts={name:math.floor(q) for name,q in quotas.items()}
    left=count-sum(counts.values())
    order=sorted(counts,key=lambda n:(-(quotas[n]-counts[n]),n))
    for name in order[:left]:counts[name]+=1
    if sum(counts.values())!=count:raise ValueError('inconsistent integer allocation')
    return counts


class Transport:
    def __init__(self, spec, timeout):
        self.name = spec.get('display_name',spec['name'])
        self.proc=None;self.sock=None;self.reader=None;self.writer=None
        self.affinity=()
        self.timeout=timeout;self.q=queue.Queue();self.dead=threading.Event()
        self.stderr_tail=deque(maxlen=24);self.stderr_lock=threading.Lock()
        if spec['type']=='tcp':
            self.sock=socket.create_connection((spec['host'],int(spec['port'])),timeout)
            self.sock.settimeout(.25)
            if spec.get('discovered_id'):self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
            telemetry('⚡', self.name, f'TCP [{spec["host"]}:{spec["port"]}]')
        else:
            # On Windows shlex(posix=False) preserves enclosing double quotes in
            # tokens. Popen(list) does NOT remove them: they become literal
            # bytes in argv, and a valid NNUE path therefore cannot be opened.
            raw_args=shlex.split(spec.get('args',''),posix=(sys.platform!='win32'))
            if sys.platform=='win32':
                raw_args=[a[1:-1] if len(a)>=2 and a[0]==a[-1] and a[0] in ('\"', "'") else a
                          for a in raw_args]
            cmd=[str(spec['path'])]+raw_args
            if not Path(cmd[0]).is_file():raise FileNotFoundError('UCI executable not found: '+cmd[0])
            telemetry('⚡', self.name, f'UCI {repr(cmd[:1])}')
            telemetry_args(self.name, cmd[1:]) if len(cmd) > 1 else None
            self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                  text=True,encoding='utf-8',errors='replace',bufsize=1)
            requested=spec.get('core',0)
            if requested:
                try:
                    self.affinity=cpu_affinity.POOL.reserve(self,requested)
                    if self.affinity:
                        cpu_affinity.apply_affinity(self.proc.pid,self.affinity)
                        telemetry('💻',self.name,f'core={requested} assigned={len(self.affinity)} affinity={list(self.affinity)}')
                    if len(self.affinity)<requested:
                        telemetry('⚠️',self.name,f'CPU affinity requested={requested} assigned={len(self.affinity)}'+(' unrestricted fallback; may share CPUs' if not self.affinity else ''))
                except Exception as exc:
                    # A partial affinity change is possible on Linux. Restart without
                    # affinity instead of keeping a partially pinned process.
                    telemetry('⚠️',self.name,f'CPU affinity unavailable: {exc}; unrestricted fallback')
                    if self.affinity:
                        self.close()
                        self.dead.clear()
                        self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            text=True,encoding='utf-8',errors='replace',bufsize=1)
            self.writer=self.proc.stdin;self.reader=self.proc.stdout
            threading.Thread(target=self._stderr,daemon=True,name='uci-stderr').start()
        threading.Thread(target=self._read,daemon=True,name='uci-reader').start()

    def _stderr(self):
        try:
            for line in self.proc.stderr:
                line=line.rstrip()
                with self.stderr_lock:self.stderr_tail.append(line)
                telemetry('⚙️', self.name, 'stderr: '+line, verbose=True)
        except (OSError,ValueError):pass

    def _read(self):
        try:
            if self.sock:
                pending=bytearray()
                while not self.dead.is_set():
                    try:chunk=self.sock.recv(4096)
                    except socket.timeout:continue
                    if not chunk:break
                    pending+=chunk
                    if len(pending)>1024*1024:raise ValueError('UCI line too long')
                    while b'\n' in pending:
                        line,_,pending=pending.partition(b'\n')
                        self.q.put(line.decode('utf-8','replace').strip())
            else:
                for line in self.reader:self.q.put(line.strip())
        except (OSError,ValueError) as exc:LOG.debug('engine reader EOF: %s',exc)
        finally:
            self.dead.set();self.q.put(None)

    def failure_detail(self):
        if self.proc is None:return 'TCP connection closed'
        # The reader can encounter EOF slightly before the stderr thread drains.
        try:self.proc.wait(timeout=.15)
        except subprocess.TimeoutExpired:pass
        with self.stderr_lock:tail=' | '.join(self.stderr_tail)
        return f'process exit={self.proc.poll()}'+(f' stderr: {tail}' if tail else ' (no stderr captured)')

    def send(self,line):
        if self.dead.is_set():raise EOFError('engine disconnected; '+self.failure_detail())
        if self.sock:self.sock.sendall((line+'\n').encode('utf-8'))
        else:
            self.writer.write(line+'\n');self.writer.flush()
        telemetry('✉️', self.name, line)

    def recv(self,deadline,cancel=None):
        while True:
            if cancel is not None and cancel.is_set():raise InterruptedError('search cancelled')
            remain=deadline-time.monotonic()
            if remain<=0:raise TimeoutError('engine response timeout')
            try:line=self.q.get(timeout=min(.1,remain))
            except queue.Empty:continue
            if line is None:raise EOFError('engine disconnected; '+self.failure_detail())
            if re.match(r'^\s*info(?:\s|$)', line):
                # UCI info has its own marker; never repeat it as a generic response.
                telemetry('ℹ️', self.name, line)
            elif re.match(r'^\s*bestmove(?:\s|$)', line):
                # Search results are logged once, after validation in analyze().
                pass
            else:
                telemetry('📮', self.name, line)
            return line

    def until(self,word,seconds):
        end=time.monotonic()+seconds;lines=[]
        while True:
            line=self.recv(end)
            lines.append(line)
            if line==word:return lines

    def close(self):
        self.dead.set()
        if self.sock:
            try:self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            self.sock.close()
        if self.proc:
            try:
                if self.proc.poll() is None:
                    self.proc.terminate();self.proc.wait(timeout=.4)
            except (OSError,subprocess.TimeoutExpired):
                try:self.proc.kill();self.proc.wait(timeout=1)
                except (OSError,subprocess.TimeoutExpired):pass
            for f in (self.proc.stdin,self.proc.stdout,self.proc.stderr):
                try:f.close()
                except (OSError,ValueError):pass
        if self.proc is None or self.proc.poll() is not None:
            cpu_affinity.POOL.release(self);self.affinity=()


@dataclass
class WorkResult:
    name:str
    best:str
    infos:dict
    elapsed_ms:int
    nps:int=0
    nodes:int=0
    uci_time_ms:int|None=None
    simulations:int|None=None


class Endpoint:
    def __init__(self,spec,static=True):
        self.spec=dict(spec);self.name=spec['name'];self.static=static
        self.transport=None;self.lock=threading.RLock();self.busy=False
        self.last_test_ms=None;self.test_nps=0;self.priority=0.0;self.probe_count=1;self.claimed_priority=0.0
        self.kmin=float(spec.get('kmin',0.0));self.kmax=float(spec.get('kmax',1.0))
        self.remote_id=None;self.support_qdepth=False
        self.next_retry=0.0;self.last_seen=time.monotonic();self.connecting=False;self.attempted=False;self.reserved=False

    @property
    def display_name(self):
        return self.spec.get('display_name',self.name)

    def available(self):
        with self.lock:return self.transport is not None and not self.busy and not self.transport.dead.is_set()

    def connect(self,config,self_id):
        with self.lock:
            if self.transport is not None or self.connecting:return False
            self.connecting=True;self.attempted=True
            self.remote_id=None;self.support_qdepth=False
            trans=None
            try:
                trans=Transport(self.spec,float(config['connect_timeout_s']))
                trans.send('uci (master)' if self.spec.get('discovered_id') else 'uci');handshake=trans.until('uciok',float(config['handshake_timeout_s']))
                for line in handshake:
                    if line.startswith('option name HiveNodeID '):
                        self.remote_id=line.split(' default ',1)[-1].strip()
                    if line.startswith('option name QDepth '):self.support_qdepth=True
                if self.spec.get('discovered_id'):
                    if self.remote_id!=self.spec['discovered_id'] or not config.get('master'):
                        raise ValueError('invalid subordinate handshake identity or role')
                elif self.remote_id:
                    raise ValueError('Hive links must use master discovery, not static TCP engines')
                # Engine-specific UCI options, e.g. Stockfish Threads/Hash.
                # These are protocol commands, not executable CLI arguments.
                for key,value in self.spec.get('options',{}).items():
                    trans.send(f'setoption name {key} value {value}')
                trans.send('isready');trans.until('readyok',float(config['handshake_timeout_s']))
                self.transport=trans
                telemetry('✅', self.display_name, f'connected type={self.spec["type"]} remote_id={self.remote_id}')
                return True
            except Exception as ex:
                telemetry('⛔', self.display_name, f'error while connecting: {ex}')
                LOG.warning('CONNECT ERROR %s: %s',self.display_name,ex)
                if trans:trans.close()
                return False
            finally:self.connecting=False

    def drop(self):
        with self.lock:
            t=self.transport;self.transport=None;self.last_test_ms=None;self.test_nps=0
            if t:t.close()

    def analyze(self,position,moves,depth,qdepth,budget_ms,cancel=None):
        with self.lock:
            if self.transport is None or self.busy:raise RuntimeError('endpoint unavailable')
            self.busy=True;t=self.transport
        started=time.monotonic()
        try:
            # Important: no UCI commands from other searches can interleave here.
            t.send(position)
            if qdepth is not None and self.support_qdepth:
                t.send(f'setoption name QDepth value {qdepth}')
                t.send('isready');t.until('readyok',max(1.,t.timeout))
            cmd=f'go depth {depth} movetime {budget_ms} searchmoves '+ ' '.join(moves)
            t.send(cmd)
            deadline=time.monotonic()+budget_ms/1000+float(t.timeout)
            infos={};recent=None;last_nps=0;last_nodes=0;last_time=None;last_simulations=None;best=None;engine_errors=[]
            stopping=False
            while True:
                try:
                    line=t.recv(deadline,None if stopping else cancel)
                except InterruptedError:
                    t.send('stop');stopping=True
                    deadline=time.monotonic()+0.5
                    continue
                except TimeoutError:
                    if stopping:raise
                    t.send('stop');stopping=True
                    deadline=time.monotonic()+0.5
                    continue
                if line.startswith('info '):
                    if line.startswith('info string ERROR'):
                        engine_errors.append(line)
                        LOG.warning('ENGINE %s: %s',self.display_name,line)
                    data=tokens_info(line)
                    if data:
                        recent=data
                        if data['nps'] is not None:last_nps=data['nps']
                        if data['nodes'] is not None:last_nodes=data['nodes']
                        if data['time'] is not None:last_time=data['time']
                        # AlphaZero emits MCTS simulations as an explicit string
                        # field. Preserve it without mistaking it for UCI nodes.
                        match=re.search(r'\bsimulations=(\d+)\b',line)
                        if match:last_simulations=int(match.group(1))
                        if data['move'] in moves and numeric_score(data) is not None:
                            old=infos.get(data['move'])
                            if old is None or (data['depth'] or 0)>=(old['depth'] or 0):infos[data['move']]=data
                elif line.startswith('bestmove '):
                    best=line.split()[1];break
            if stopping or (cancel is not None and cancel.is_set()):
                t.send('isready');t.until('readyok',0.5)
                if best not in moves or best not in infos:
                    return WorkResult(self.name,best,infos,round((time.monotonic()-started)*1000),last_nps,last_nodes,last_time,last_simulations)
            if best not in moves:
                detail=('; '.join(engine_errors[-3:]) if engine_errors else 'no error detail from engine')
                raise ValueError('bestmove outside assigned searchmoves: '+str(best)+'; '+detail)
            if best not in infos and recent and len(moves)==1 and numeric_score(recent) is not None:
                infos[best]=dict(recent,move=best)
            if best not in infos:raise ValueError('bestmove without usable UCI score')
            inf=infos[best]
            score=f'mate {inf["mate"]}' if inf['mate'] is not None else f'cp {inf["cp"]}'
            bound='' if inf['bound']=='exact' else ' '+inf['bound']
            telemetry('🧠', self.display_name, f'{line} score {score}{bound} depth {inf["depth"] if inf["depth"] is not None else "?"} nodes {last_nodes} time {last_time if last_time is not None else "?"} nps {last_nps}')
            return WorkResult(self.name,best,infos,round((time.monotonic()-started)*1000),last_nps,last_nodes,last_time,last_simulations)
        except Exception:
            # Flush/discard an interrupted transaction; otherwise late bestmove
            # could be mistaken for the next request.
            self.drop();raise
        finally:
            with self.lock:self.busy=False


class TeamTransport:
    """Liveness facade; the registry sees a single indivisible resource."""
    def __init__(self,members):
        self.members=members;self.dead=self
    def is_set(self):
        return any(m.transport is None or m.transport.dead.is_set() for m in self.members)
    def close(self):
        for m in self.members:m.drop()


class TeamEndpoint(Endpoint):
    def __init__(self,spec):
        super().__init__(spec)
        self.members=[Endpoint(dict(m,display_name=self.name+'/'+m['name'])) for m in spec['members']]

    def connect(self,config,self_id):
        with self.lock:
            if self.transport is not None or self.connecting:return False
            self.connecting=True;self.attempted=True
            try:
                for m in self.members:
                    if not m.connect(config,self_id):
                        for member in self.members:member.drop()
                        return False
                self.transport=TeamTransport(self.members)
                telemetry('✅',self.name,f'connected team members={len(self.members)}')
                return True
            finally:self.connecting=False

    def analyze(self,position,moves,depth,qdepth,budget_ms,cancel=None):
        with self.lock:
            if not self.available():raise RuntimeError('team unavailable')
            self.busy=True
        start=time.monotonic();end=start+budget_ms/1000
        infos={};nodes=0
        try:
            # Restrict every member to exactly one identical root move. A single
            # multi-move UCI request cannot guarantee scores for all candidates.
            for i,move in enumerate(moves):
                if (cancel is not None and cancel.is_set()) or time.monotonic()>=end:break
                share=max(1,int((end-time.monotonic())*1000/(len(moves)-i)))
                replies=queue.Queue();workers=[];local_stop=threading.Event()
                def run(member):
                    try:replies.put((member,member.analyze(position,[move],depth,qdepth,share,local_stop),None))
                    except Exception as ex:replies.put((member,None,ex))
                for member in self.members:
                    t=threading.Thread(target=run,args=(member,),daemon=True);workers.append(t);t.start()
                results={};failure=None
                # Propagate parent cancellation; allow normal Endpoint stop/drain.
                stop_at=min(end,time.monotonic()+share/1000)
                while len(results)<len(self.members):
                    if time.monotonic()>=stop_at or (cancel is not None and cancel.is_set()):local_stop.set()
                    try:member,result,error=replies.get(timeout=.02)
                    except queue.Empty:continue
                    results[member.name]=result
                    if error is not None:failure=error;local_stop.set()
                for t in workers:t.join()
                nodes+=sum(r.nodes for r in results.values() if r is not None)
                if failure is not None:raise RuntimeError('team member failed: '+str(failure))
                samples=[]
                for member in self.members:
                    result=results[member.name]
                    inf=result.infos.get(move) if result is not None else None
                    if not inf or inf['bound']!='exact' or numeric_score(inf) is None:break
                    samples.append((member.spec['reliability'],inf))
                if len(samples)!=len(self.members):
                    telemetry('⚠️',self.name,'incomplete joint evaluation move='+move);continue
                cp=round(math.fsum(w*numeric_score(inf) for w,inf in samples))
                # Preserve a weighted numeric estimate, never manufacture a
                # forced mate from a mixture of independent engine scores.
                mate=None
                elapsed=max(1,round((time.monotonic()-start)*1000))
                infos[move]=dict(move=move,cp=cp if mate is None else None,mate=mate,bound='exact',depth=min(inf['depth'] or 0 for _,inf in samples),nodes=nodes,time=elapsed,nps=nodes*1000//elapsed)
                telemetry('⚙️',self.name,f'fusion move={move} score_cp={cp} members={len(samples)}',verbose=True)
            elapsed=max(1,round((time.monotonic()-start)*1000))
            best=max(infos,key=lambda m:numeric_score(infos[m])) if infos else '0000'
            if best!='0000':telemetry('🧠',self.name,f'bestmove {best} score cp {numeric_score(infos[best])} depth {infos[best]["depth"]} nodes {nodes} time {elapsed} nps {nodes*1000//elapsed}')
            return WorkResult(self.name,best,infos,elapsed,nodes*1000//elapsed,nodes,elapsed)
        finally:
            with self.lock:self.busy=False


class Registry:
    def __init__(self,config,node_id):
        self.config=config;self.node_id=node_id;self.lock=threading.RLock()
        self.items={e['name']:(TeamEndpoint(e) if e['type']=='team' else Endpoint(e)) for e in config['engines']}
        self.clone_sequence=0
        self.calibration_lock=threading.RLock()
        self.last_full_calibration=None;self.calibration_pending=False;self.calibrating=False
        self.allocation={};self.membership=None;self.allocation_error=None;self.starting=True
        self.periodic_retry_at=0.0
        self.calibration_cancel=threading.Event()
        self.calibration_forced=False
        self.search_requests=0
        self.beacon_revision=0;self.beacon_engines=[]
        self.stopped=threading.Event();self.monitor=None;self.discover_pending=set()

    def snapshot(self):
        with self.lock:return list(self.items.values())

    def display_name(self,name):
        with self.lock:
            ep=self.items.get(name)
            return ep.display_name if ep is not None else name

    def active(self):return [x for x in self.snapshot() if x.available() and not x.reserved]

    def ready(self):
        with self.lock:
            ready=[]
            for e in self.items.values():
                transport=e.transport
                if transport is not None and not transport.dead.is_set() and e.last_test_ms is not None:
                    ready.append(e)
            return ready

    def mark_due(self,now):
        # Called with registry lock held. Close admission immediately at the
        # maximum interval, even if the maintenance thread is between ticks.
        if (not self.starting and self.last_full_calibration is not None and
            now>=self.periodic_retry_at and self.ready() and
            self.config['recalibration_max'] != -1 and
            now-self.last_full_calibration>=60*self.config['recalibration_max'] and
            not self.calibration_pending):
            self.calibration_pending=True
            telemetry('🕛','Hive','maximum interval reached; draining active searches')

    def begin_search(self):
        with self.lock:
            self.search_requests+=1
            if self.calibrating and not self.calibration_forced:
                self.calibration_cancel.set()

    def end_search(self):
        with self.lock:
            self.search_requests-=1

    def claim(self, excluded=None):
        # Reserve against a single published generation, never a partly calibrated set.
        with self.lock:
            if excluded is not None:excluded.clear()
            self.mark_due(time.monotonic())
            if self.starting or self.calibrating or self.calibration_pending:return []
            self.weights()
            if self.allocation_error:return []
            ready=self.ready();result=[]
            for ep in ready:
                with ep.lock:
                    if ep.available() and not ep.reserved:result.append(ep)
                    elif excluded is not None:excluded[ep.name]=(ep.kmin,'BUSY' if ep.busy else 'RESERVED')
            # Keep concurrent sessions possible only when their available subset
            # can satisfy the same bounds; never silently normalize past a cap.
            if not result:return []
            try:
                shares=self.allocation.copy() if len(result)==len(ready) else self.effective_priorities(result)
            except ValueError:return []
            if not result:return []
            for ep in result:
                with ep.lock:ep.reserved=True;ep.claimed_priority=shares[ep.name]
            if excluded is not None:
                for ep in self.items.values():
                    if ep not in ready:excluded[ep.name]=(ep.kmin,'CONNECTING' if ep.connecting else 'DISCONNECTED' if ep.transport is None else 'DEAD_TRANSPORT' if ep.transport.dead.is_set() else 'UNCALIBRATED')
            return result

    def waiting_for_resources(self):
        with self.lock:
            return self.starting or self.calibrating or self.calibration_pending or self.has_connected_busy() or any(e.connecting for e in self.items.values())

    def release(self,ep):
        with ep.lock:ep.reserved=False

    def has_connected_busy(self):
        with self.lock:
            return any(e.busy or e.reserved for e in self.ready())

    def spawn_local_if_needed(self):
        with self.calibration_lock:
            with self.lock:
                self.mark_due(time.monotonic())
                if self.calibration_pending or self.calibrating or self.starting or self.allocation_error:return None
            return self._spawn_local_if_needed()

    def _spawn_local_if_needed(self):
        """Create one independent local process for a concurrent UCI session.

        A local executable is a reusable template; its subprocess is NOT shared
        between concurrent searches. The new process receives its own UCI probe.
        """
        with self.lock:
            templates=[e for e in self.items.values() if e.static and
                       e.spec['type']=='uci' and '#instance-' not in e.name and
                       e.transport is not None and not e.transport.dead.is_set() and
                       e.last_test_ms is not None]
            if not templates:return None
            # Prefer a template already known to be operational.
            source=min(templates,key=lambda e:(e.transport is None,e.last_test_ms or float('inf')))
            self.clone_sequence+=1
            spec=dict(source.spec)
            spec['name']=source.name+'#instance-'+str(self.clone_sequence)
            # A clone is a new worker, not another copy of a configured minimum.
            spec.pop('kmin',None);spec.pop('kmax',None)
            clone=Endpoint(spec,static=False)
            clone.reserved=True
            self.items[clone.name]=clone
        telemetry('⚡', clone.name, f'new UCI instance from {source.name}')
        if clone.connect(self.config,self.node_id):
            try:
                self.test(clone)
                with clone.lock:clone.reserved=False
                self.weights()
                return clone
            except Exception as exc:
                LOG.exception('LOCAL INSTANCE FAILED %s: %s',clone.name,exc)
        clone.drop()
        with self.lock:self.items.pop(clone.name,None)
        self.weights()
        return None

    @staticmethod
    def effective_priorities(endpoints):
        eps=1e-9
        if not endpoints:raise ValueError('no calibrated engines')
        if any(not (0<=e.kmin<e.kmax<=1) for e in endpoints):raise ValueError('invalid engine bounds')
        low=math.fsum(e.kmin for e in endpoints);high=math.fsum(e.kmax for e in endpoints)
        if low>1+eps or high<1-eps:raise ValueError(f'inconsistent resources sum(Kmin)={low:.9f} sum(Kmax)={high:.9f}')
        if any(e.last_test_ms is None or not math.isfinite(e.last_test_ms) or e.last_test_ms<=0 for e in endpoints):raise ValueError('invalid wall time')
        # Scale inverse latencies to avoid overflow; the common factor cancels.
        fastest=min(e.last_test_ms for e in endpoints)
        c={e.name:fastest/e.last_test_ms for e in endpoints}
        k={e.name:e.kmin for e in endpoints}
        for _ in range(len(endpoints)):
            r=1-math.fsum(k.values())
            if r<=eps:break
            active=[e for e in endpoints if k[e.name]<e.kmax]
            if not active:break
            total=math.fsum(c[e.name] for e in active)
            for e in active:k[e.name]=min(e.kmax,k[e.name]+r*c[e.name]/total)
        if abs(math.fsum(k.values())-1)>eps or any(not e.kmin-eps<=k[e.name]<=e.kmax+eps for e in endpoints):raise ValueError('inconsistent final allocation')
        return k

    def weights(self,force=False):
        with self.lock:
            ready=self.ready()
            membership=tuple(sorted((e.name,id(e.transport),e.last_test_ms) for e in ready))
            if not force and (self.starting or self.calibrating or membership==self.membership):return ready
            self.membership=membership
            # Publish a local-only snapshot from the same completed calibration.
            local=[e for e in ready if not e.spec.get('discovered_id')]
            try:self.beacon_engines=hive_beacon.effective_times(local,self.effective_priorities(local))
            except (ValueError,OverflowError,ZeroDivisionError):self.beacon_engines=[]
            self.beacon_revision+=1
            try:shares=self.effective_priorities(ready)
            except ValueError as ex:
                self.allocation={};self.allocation_error=str(ex)
                for e in self.items.values():e.priority=0.0
                telemetry('⛔','Hive',self.allocation_error)
                return ready
            self.allocation=shares;self.allocation_error=None
            for e in self.items.values():e.priority=shares.get(e.name,0.0)
            for name,share in sorted(shares.items()):telemetry('⚖️',self.display_name(name),f'{share:.8f}')
            telemetry('⚖️','Hive',f'total={math.fsum(shares.values()):.8f}')
            return ready

    def startup(self):
        for ep in self.snapshot():
            if self.stopped.is_set():break
            self._connect_and_test(ep)
        with self.lock:
            self.weights(force=True)
            if self.allocation_error:raise ValueError(self.allocation_error)
            self.last_full_calibration=time.monotonic();self.starting=False

    def periodic(self,now=None):
        now=time.monotonic() if now is None else now
        with self.lock:
            if self.starting or self.calibrating or self.last_full_calibration is None:return
            age=now-self.last_full_calibration
            if age<60*self.config['recalibration_min']:return
            if now<self.periodic_retry_at:return
            forced=self.config['recalibration_max'] != -1 and age>=60*self.config['recalibration_max']
            self.mark_due(now)
            if not forced and self.search_requests:return
            if any(e.busy or e.reserved or e.connecting for e in self.items.values()):return
            if not self.ready():
                self.calibration_pending=False
                return
            self.calibration_pending=True;self.calibrating=True
            self.calibration_forced=forced
            self.calibration_cancel.clear()
        with self.calibration_lock:
            ready=[];previous={}
            try:
                with self.lock:
                    ready=self.ready()
                    for e in ready:
                        e.reserved=True
                        previous[e]=(e.transport,e.last_test_ms,e.test_nps)
                telemetry('🕛','Hive',f'periodic recalibration started forced={forced} engines={sum(not e.spec.get("discovered_id") for e in ready)}')
                for e in ready:
                    if self.stopped.is_set() or self.calibration_cancel.is_set():break
                    if e.spec.get('discovered_id'):continue
                    try:self.test(e)
                    except InterruptedError:
                        break
                    except Exception as ex:
                        telemetry('⛔',e.display_name,f'recalibration failed: {ex}');e.drop()
                with self.lock:
                    if self.calibration_cancel.is_set() or self.stopped.is_set():
                        # Restore only still-live original transports. Do not resurrect failures.
                        for e,(transport,ms,nps) in previous.items():
                            if not e.spec.get('discovered_id') and e.transport is transport and transport is not None and not transport.dead.is_set():
                                e.last_test_ms=ms;e.test_nps=nps
                        self.weights(force=True)
                        telemetry('🕛','Hive','periodic recalibration interrupted; previous valid measurements retained')
                        return
                    self.weights(force=True)
                    if not self.allocation_error and ready and not self.stopped.is_set():
                        self.last_full_calibration=time.monotonic();self.periodic_retry_at=0.0
                    else:
                        self.periodic_retry_at=time.monotonic()+float(self.config['retry_seconds'])
                telemetry('🕛','Hive','periodic recalibration '+('failed' if self.allocation_error else 'completed'))
            finally:
                with self.lock:
                    for e in ready:e.reserved=False
                    self.calibrating=False;self.calibration_pending=False;self.calibration_forced=False

    def test(self,ep):
        """Measure one ordinary engine; discovered Hive capacities are advertised."""
        if ep.spec.get('discovered_id'):raise ValueError('remote Hive must not be probed')
        b=chess.Board(self.config['test']['fen']);move=self.config['test']['move']
        if chess.Move.from_uci(move) not in b.legal_moves:raise ValueError('invalid test move')
        position='position fen '+b.fen()
        telemetry('✅', ep.name, f'test FEN={b.fen()} move={move}')
        if ep.spec['type']=='uci':
            telemetry_args(ep.name, [ep.spec['path']] + shlex.split(ep.spec.get('args',''), posix=True))
        elif ep.spec['type']=='team':
            telemetry('⚙️',ep.name,f'joint test members={len(ep.members)}')
        else:
            telemetry('⚙️', ep.name, f'TCP {ep.spec.get("host")}:{ep.spec.get("port")}')
        depth=int(self.config['test']['depth']);qdepth=self.config['test']['qdepth']
        budget=int(self.config['test']['movetime_ms'])
        started_ns=time.perf_counter_ns()
        cancel=self.calibration_cancel if self.calibrating else None
        result=ep.analyze(position,[move],depth,qdepth,budget,cancel)
        if cancel is not None and cancel.is_set():raise InterruptedError('voluntary calibration cancelled')
        if result.best != move or move not in result.infos:raise ValueError('test has no complete scored result')
        ep.last_test_ms=max(1,time.perf_counter_ns()-started_ns)/1_000_000;ep.test_nps=max(0,result.nps)
        # Distinguish measured end-to-end wall time from the engine's UCI
        # search time. NPS is an engine-provided metric: for AlphaZero its
        # nodes are MCTS tree nodes, not alpha-beta nodes. Never imply
        # that either metric is directly comparable across algorithms.
        telemetry('⚙️', ep.name,
                  f'wall_test_ms={ep.last_test_ms:.6f} kmin={ep.kmin:.6f} kmax={ep.kmax:.6f} uci_time_ms={result.uci_time_ms} '
                  f'uci_nodes={result.nodes} uci_nps={ep.test_nps} '
                  f'mcts_simulations={result.simulations} cp={result.infos[result.best].get("cp")}')
        LOG.info('TEST %s jobs=1 wall_ms=%s uci_time_ms=%s '
                 'uci_nodes=%s uci_nps=%s mcts_simulations=%s cp=%s '
                 'depth_requested=%s movetime_requested_ms=%s',
                 ep.name,ep.last_test_ms,result.uci_time_ms,result.nodes,
                 ep.test_nps,result.simulations,result.infos[result.best].get('cp'),
                 depth,budget)
        return

    def _connect_and_test(self,ep):
        with self.calibration_lock:
            if self.stopped.is_set():return
            with self.lock:
                if (self.calibrating or self.calibration_pending) and self.ready():return
            return self._connect_and_test_locked(ep)

    def _connect_and_test_locked(self,ep):
        with self.lock:ep.reserved=True
        if ep.connect(self.config,self.node_id):
            try:
                if ep.spec.get('discovered_id'):
                    with self.lock:ep.last_test_ms=ep.spec['advertised_ms']
                else:self.test(ep)
            except Exception as ex:
                telemetry('⛔', ep.display_name, f'test failed: {ex}')
                LOG.warning('TEST FAILED %s: %s',ep.display_name,ex);ep.drop()
            finally:
                with self.lock:
                    ep.reserved=False
                    if not self.starting:self.weights()
        else:
            with ep.lock:ep.reserved=False

    def maintain(self):
        while not self.stopped.is_set():
            now=time.monotonic()
            self.periodic(now)
            for ep in self.snapshot():
                if self.stopped.is_set():break
                transport=ep.transport
                if transport and transport.dead.is_set() and not ep.busy and not ep.reserved:
                    ep.drop();self.weights()
                if ep.transport is None and ep.static and not ep.connecting and not ep.busy and not ep.reserved and now>=ep.next_retry and (not self.calibration_pending or not self.ready()):
                    ep.next_retry=now+float(self.config['retry_seconds'])
                    self._connect_and_test(ep)
            self.weights()
            self.stopped.wait(.3)

    def discovered(self,advert):
        if not self.config.get('master') or advert['master'] or advert['node_id']==self.node_id:return
        their_id=advert['node_id'];name='discovered-'+their_id
        ms=hive_beacon.aggregate_ms(advert['engines'])
        with self.lock:
            ep=self.items.get(name)
            if ep is None:
                if ms is None:return
                ep=Endpoint(dict(name=name,display_name=advert['name'],type='tcp',host=advert['ip'],port=advert['tcp_port'],
                                 discovered_id=their_id,advertised_ms=ms),static=False)
                self.items[name]=ep
            # Name is presentation only; identity and allocation remain keyed by node ID.
            ep.spec['display_name']=advert['name']
            if ep.transport is not None:
                ep.transport.name=ep.display_name
            if ms is None:
                ep.spec['advertised_ms']=None;ep.last_test_ms=None
                # Keep the single connection, but remove its capacity immediately.
                self.weights();return
            if ep.transport is not None and not ep.transport.dead.is_set():
                ep.spec['advertised_ms']=ms;ep.last_test_ms=ms
                self.weights();return
            ep.spec['advertised_ms']=ms
            if ep.busy or ep.reserved or ep.connecting or name in self.discover_pending:return
            if ep.transport is not None:ep.drop()
            ep.spec.update(host=advert['ip'],port=advert['tcp_port'])
            self.discover_pending.add(name)
        def connect_once():
            try:self._connect_and_test(ep)
            finally:
                with self.lock:self.discover_pending.discard(name)
        threading.Thread(target=connect_once,daemon=True).start()

    def advertised_engines(self):
        with self.lock:
            return [dict(e) for e in self.beacon_engines]

    def stop(self):
        self.stopped.set()
        for ep in self.snapshot():ep.drop()


class Discovery:
    def __init__(self,config,registry,node_id):
        self.cfg=config;self.registry=registry;self.node_id=node_id
        self.stop=threading.Event();self.sock=None;self.sequence=0
        self.boot_id=uuid.uuid4().hex;self.seen={};self.masters={}
        self.changed=threading.Event()

    def local_ip(self):
        bind=self.cfg.get('advertise_ip')
        if bind:return bind
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:s.connect(('192.0.2.1',9));return s.getsockname()[0]
        except OSError:return '127.0.0.1'
        finally:s.close()

    def announce(self,event='UPDATE'):
        self.sequence+=1
        payload=dict(protocol='HIVE',version=1,event=event,node_id=self.node_id,
            boot_id=self.boot_id,sequence=self.sequence,name=self.cfg['name'],
            ip=self.local_ip(),tcp_port=int(self.cfg['tcp_port']),master=self.cfg.get('master',False),
            engines=[] if event=='SHUTDOWN' else self.registry.advertised_engines())
        return json.dumps(payload,separators=(',',':'),allow_nan=False).encode('utf-8')

    def receive(self,data):
        advert=hive_beacon.decode(data)
        if advert['node_id']==self.node_id:return False
        key=(advert['node_id'],advert['boot_id'])
        if advert['sequence']<=self.seen.get(key,0):return False
        self.seen[key]=advert['sequence']
        telemetry('📡',advert['name'],f'RX {advert["event"]} master={advert["master"]} engines={len(advert["engines"])}')
        telemetry('📡',advert['name'],data.decode('utf-8'),verbose=True)
        if advert['master']:
            if advert['event']=='SHUTDOWN':
                self.masters.pop(advert['node_id'],None);return False
            now=time.monotonic();expiry=max(60,3*60*self.cfg['broadcast'])
            self.masters={k:v for k,v in self.masters.items() if now-v<expiry}
            new=advert['node_id'] not in self.masters
            self.masters[advert['node_id']]=now
            if new and (self.cfg.get('master') or len(self.masters)>1):
                telemetry('⚠️','Hive','MULTIPLE MASTERS DETECTED: '+advert['name'])
        else:self.registry.discovered(advert)
        return advert['event']=='STARTUP'

    def run(self):
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock=s
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            s.bind(('',int(self.cfg['udp_port'])));s.settimeout(.25)
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as tx:
                tx.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
                def send(event):
                    try:
                        payload=self.announce(event)
                        tx.sendto(payload,('255.255.255.255',int(self.cfg['udp_port'])))
                        telemetry('📡',self.cfg['name'],f'TX {event}')
                        telemetry('📡',self.cfg['name'],payload.decode('utf-8'),verbose=True)
                    except (OSError,ValueError) as ex:telemetry('⚠️','Hive',f'broadcast failed: {ex}')
                revision=self.registry.beacon_revision;send('STARTUP')
                next_tx=time.monotonic()+60*self.cfg['broadcast']
                while not self.stop.is_set():
                    current=self.registry.beacon_revision
                    if current!=revision or self.changed.is_set():
                        self.changed.clear();revision=current;send('UPDATE')
                    if time.monotonic()>=next_tx:
                        send('HEARTBEAT');next_tx=time.monotonic()+60*self.cfg['broadcast']
                    try:data,_=s.recvfrom(65535)
                    except socket.timeout:continue
                    except OSError:
                        if self.stop.is_set():break
                        raise
                    try:
                        if self.receive(data):send('RESPONSE')
                    except (ValueError,UnicodeError,TypeError,OverflowError):continue
                if self.stop.is_set():send('SHUTDOWN')
        except OSError as ex:
            if not self.stop.is_set():telemetry('⛔','Hive',f'UDP discovery failed: {ex}')
        finally:s.close()


class Session:
    def __init__(self,hive,emit,label):
        self.hive=hive;self.emit=emit;self.label=label
        self.board=chess.Board();self.position='position startpos'
        self.stop=threading.Event();self.search_thread=None
        self.search_lock=threading.Lock();self.closed=False;self.workers=[]

    def send(self,line):
        if not self.closed:
            telemetry('⬅️', self.label, line)
            self.emit(line)

    def set_position(self,parts):
        if not parts:raise ValueError('empty position')
        if parts[0]=='startpos':b=chess.Board();i=1
        elif parts[0]=='fen':
            if len(parts)<7:raise ValueError('incomplete FEN')
            b=chess.Board(' '.join(parts[1:7]));i=7
        else:raise ValueError('position requires startpos or fen')
        if i<len(parts):
            if parts[i]!='moves':raise ValueError('invalid position suffix')
            for v in parts[i+1:]:
                move=chess.Move.from_uci(v)
                if move not in b.legal_moves:raise ValueError('illegal move: '+v)
                b.push(move)
        self.board=b;self.position='position '+' '.join(parts)

    def go(self,text):
        tokens=text.split();i=0;depth=self.hive.cfg['depth'];qdepth=getattr(self,'qdepth_override',self.hive.cfg['qdepth']);budget=self.hive.cfg['timeout_ms'];restricted=None
        clock={};explicit_movetime=False
        keys=('depth','qdepth','movetime','wtime','btime','winc','binc','movestogo')
        while i<len(tokens):
            key=tokens[i]
            if key=='searchmoves':
                restricted=[];i+=1
                while i<len(tokens) and tokens[i] not in keys:
                    restricted.append(tokens[i]);i+=1
                continue
            if key in keys:
                if i+1>=len(tokens):raise ValueError('go '+key+' missing value')
                n=int(tokens[i+1]);i+=2
                if n<0 or (n==0 and key in ('depth','movetime','movestogo')):raise ValueError('go '+key+' invalid')
                if key=='depth':depth=min(depth,n)
                elif key=='qdepth':qdepth=min(qdepth,n)
                elif key=='movetime':budget=min(budget,n);explicit_movetime=True
                else:clock[key]=n
            else:raise ValueError('unsupported go parameter: '+key)
        clock_deadline=None
        side='w' if self.board.turn else 'b'
        if side+'time' in clock:
            remaining=clock[side+'time'];increment=clock.get(side+'inc',0)
            # Keep time for transport and final response; never spend the increment
            # before it has actually been credited by the external chess clock.
            reserve=min(250,max(10,remaining//10))
            usable=max(1,remaining-reserve)
            if not explicit_movetime:
                horizon=clock.get('movestogo',30)
                budget=min(budget,max(1,remaining//horizon+increment*3//4))
            budget=min(budget,usable)
            grace=min(int(float(self.hive.cfg['search_grace_s'])*1000),max(0,usable-budget))
            clock_deadline=time.monotonic()+(budget+grace)/1000
            telemetry('⚙️',self.label,f'clock side={side} remaining={remaining} increment={increment} budget={budget} ms')
        elif 'wtime' in clock or 'btime' in clock:
            raise ValueError('go missing clock for side to move: '+side+'time')
        valid={m.uci() for m in self.board.legal_moves}
        if restricted is None:moves=sorted(valid)
        else:
            if not restricted or len(restricted)!=len(set(restricted)) or any(x not in valid for x in restricted):
                raise ValueError('invalid searchmoves')
            moves=restricted
        with self.search_lock:
            if self.search_thread and self.search_thread.is_alive():raise RuntimeError('session busy')
            self.stop=threading.Event()
            self.workers=[t for t in self.workers if t.is_alive()]
            if not moves:self.send('bestmove 0000');return
            registry=self.hive.registry
            registry.begin_search()
            def search():
                try:self._search(self.position,moves,depth,qdepth,budget,clock_deadline)
                finally:registry.end_search()
            t=threading.Thread(target=search,daemon=True)
            self.search_thread=t
            try:t.start()
            except BaseException:
                registry.end_search();raise

    def _search(self,position,moves,depth,qdepth,budget,clock_deadline=None):
        start=time.monotonic();eps=[];excluded={}
        # Reservation is per UCI session. Never place work on busy endpoints.
        # TCP-only contention waits for resources even beyond the UCI movetime;
        # the actual search budget begins once a resource is acquired.
        # Local UCI engines can be replicated into independent processes.
        while not self.stop.is_set() and not self.hive.stopped.is_set() and not self.closed:
            if clock_deadline is not None and time.monotonic()>=clock_deadline:break
            if (self.hive.registry.calibration_pending or self.hive.registry.calibrating) and time.monotonic()>=start+budget/1000+float(self.hive.cfg['search_grace_s']):break
            eps=self.hive.registry.claim(excluded)
            if eps:break
            if self.hive.registry.has_connected_busy() and not self.hive.registry.calibration_pending and not self.hive.registry.calibrating and any(e.static and e.spec['type']=='uci' for e in self.hive.registry.snapshot()):
                ep=self.hive.registry.spawn_local_if_needed()
                if ep:
                    eps=self.hive.registry.claim(excluded)
                    if eps:break
            if not self.hive.registry.waiting_for_resources():
                report_exclusions(self.label,excluded,self.hive.registry.display_name)
                self.send('info string Hive '+(self.hive.registry.allocation_error or 'no connected engines'));self.send('bestmove 0000');return
            time.sleep(.025)
        if not eps:
            if excluded:report_exclusions(self.label,excluded,self.hive.registry.display_name)
            self.send('info string Hive search cancelled while waiting for an engine; no evaluated move');self.send('bestmove 0000');return
        # Waiting for a busy TCP engine is outside the requested thinking budget.
        search_start=time.monotonic()
        if clock_deadline is not None:
            budget=min(budget,max(1,int((clock_deadline-search_start)*1000)))
        weights={e.name:e.claimed_priority for e in eps}
        buckets={e.name:[] for e in eps}
        try:counts=apportion_moves(weights,len(moves))
        except ValueError as ex:
            for e in eps:self.hive.registry.release(e)
            telemetry('⛔','Hive',str(ex));self.send('info string Hive ERROR '+str(ex));self.send('bestmove 0000');return
        # Preserve round-robin spreading of root moves rather than contiguous blocks.
        for m in moves:
            e=min((e for e in eps if len(buckets[e.name])<counts[e.name]),key=lambda x:(len(buckets[x.name])+1)/weights[x.name])
            buckets[e.name].append(m)
        work=[(e,buckets[e.name]) for e in eps if buckets[e.name]]
        for e in eps:
            if not buckets[e.name]:
                excluded[e.name]=(e.kmin,'ZERO_WEIGHT' if weights[e.name]==0 else 'NO_MOVES_ASSIGNED')
                self.hive.registry.release(e)
        report_exclusions(self.label,excluded,self.hive.registry.display_name)
        telemetry('⚙️', self.label, 'assigned '+str(sum(len(ms) for _,ms in work))+'/'+str(len(moves))+' '+ ' '.join(f'{e.display_name}={len(ms)} ({weights[e.name]:.3f})' for e,ms in [(e,buckets[e.name]) for e in eps])+(' '+ ' '.join(f'{self.hive.registry.display_name(name)}=0 ({k:.3f})' if k is not None else f'{self.hive.registry.display_name(name)}=0 (auto)' for name,(k,reason) in excluded.items() if name not in buckets) if any(name not in buckets for name in excluded) else ''))
        replies=queue.Queue()
        cancel=self.stop
        def run(ep,assigned):
            r=None
            try:r=ep.analyze(position,assigned,depth,qdepth,budget,cancel)
            except Exception as ex:LOG.warning('WORK %s failed %s',ep.display_name,ex)
            finally:
                self.hive.registry.release(ep)
                replies.put(r)
        for ep,assigned in work:
            worker=threading.Thread(target=run,args=(ep,assigned),daemon=True)
            self.workers.append(worker);worker.start()
        pending=len(work);results=[];deadline=search_start+budget/1000+float(self.hive.cfg['search_grace_s'])
        if clock_deadline is not None:deadline=min(deadline,clock_deadline)
        while pending and not self.stop.is_set() and time.monotonic()<deadline:
            try:r=replies.get(timeout=min(.1,max(.01,deadline-time.monotonic())))
            except queue.Empty:continue
            pending-=1
            if r:results.append(r)
        if pending:
            cancel.set()
            drain_deadline=time.monotonic()+1.2
            if clock_deadline is not None:drain_deadline=min(drain_deadline,clock_deadline)
            while pending and time.monotonic()<drain_deadline:
                try:r=replies.get(timeout=max(.001,min(.05,drain_deadline-time.monotonic())))
                except queue.Empty:continue
                pending-=1
                if r:results.append(r)
        # One standard UCI info per root move with a known score. No core IDs.
        candidates=[];n=0
        for r in results:
            n+=r.nodes
            for move,inf in r.infos.items():
                if move in moves and numeric_score(inf) is not None:
                    candidates.append((move,inf))
        exact=[x for x in candidates if x[1]['bound']=='exact']
        group=exact or candidates
        # When only bounds exist, max is provisional and not an exact comparison.
        group.sort(key=lambda x:numeric_score(x[1]),reverse=True)
        for idx,(move,inf) in enumerate(sorted(candidates,key=lambda x:numeric_score(x[1]),reverse=True),1):
            val=('mate '+str(inf['mate'])) if inf['mate'] is not None else ('cp '+str(inf['cp']))
            b=(' '+inf['bound']) if inf['bound']!='exact' else ''
            telemetry('ℹ️', self.label, 'info depth '+str(inf['depth'] or 0)+' multipv '+str(idx)+' score '+val+b+
                 ' nodes '+str(inf['nodes'] or 0)+' time '+str(inf['time'] or 0)+' pv '+move)
        if not group:
            self.send('info string Hive no valid scored result');self.send('bestmove 0000')
            return
        move,inf=group[0];val=('mate '+str(inf['mate'])) if inf['mate'] is not None else ('cp '+str(inf['cp']))
        self.send(f'info depth {inf["depth"] or 0} score {val} nodes {n} time {round((time.monotonic()-start)*1000)} pv {move}')
        self.send('bestmove '+move)

    def command(self,line):
        cmd,_,arg=line.strip().partition(' ')
        if not cmd:return True
        telemetry('➡️', self.label, line.strip())
        try:
            if cmd=='uci':
                if arg=='(master)' and self.hive.master_session is not self:return False
                self.send('id name hive')
                self.send('id author Dr. Pedro E. Colla')
                self.send('option name HiveNodeID type string default '+self.hive.node_id)
                self.send('option name QDepth type spin default '+str(self.hive.cfg['qdepth'])+' min 0 max 64')
                self.send('uciok')
            elif cmd=='isready':self.send('readyok')
            elif cmd=='ucinewgame':
                if self.search_thread and self.search_thread.is_alive():raise RuntimeError('busy')
                self.set_position(['startpos'])
            elif cmd=='position':
                if self.search_thread and self.search_thread.is_alive():raise RuntimeError('busy')
                self.set_position(arg.split())
            elif cmd=='go':self.go(arg)
            elif cmd=='setoption':
                m=re.fullmatch(r'name\s+QDepth\s+value\s+(\d+)',arg)
                if m:
                    q=int(m.group(1))
                    if not 0<=q<=64:raise ValueError('QDepth out of range')
                    # Per-session extension; never mutate the other frontend.
                    self.qdepth_override=q
            elif cmd=='stop':self.stop.set()
            elif cmd=='quit':return False
            else:LOG.debug('unsupported UCI %s',cmd)
        except Exception as exc:
            LOG.warning('SESSION %s command %s rejected: %s',self.label,cmd,exc)
            self.send('info string Hive ERROR '+str(exc).replace('\n',' '))
            if cmd=='go' and (not self.search_thread or not self.search_thread.is_alive()):self.send('bestmove 0000')
        return True

    def close(self):
        self.stop.set();self.closed=True
        # Never shut down other sessions or their searches.


class Hive:
    def __init__(self,cfg):
        self.cfg=cfg;self.node_id=cfg['node_id'];self.registry=Registry(cfg,self.node_id)
        self.stopped=threading.Event();self.threads=[];self.server=None
        self.discovery=None
        self.sessions_lock=threading.RLock()
        self.sessions=set()
        self.clients=set()
        self.shutdown_lock=threading.Lock()
        self.shutdown_started=False
        self.master_session=None

    def shutdown(self):
        """Global shutdown: cancel ALL sessions and release every owned resource."""
        with self.shutdown_lock:
            if self.shutdown_started:return
            self.shutdown_started=True
        telemetry('⛔', '', 'Hive global shutdown starting')
        self.stopped.set()
        self.registry.stopped.set()  # stop retry/connect loops before teardown
        if self.discovery:
            self.discovery.stop.set()
            sock=self.discovery.sock
            if sock:
                try:sock.close()
                except OSError:pass
        srv=self.server
        self.server=None
        if srv:
            try:srv.close()
            except OSError:pass
        with self.sessions_lock:
            sessions=list(self.sessions)
            clients=list(self.clients)
        # Cancel first so blocked UCI reads can observe cancellation.
        for session in sessions:session.close()
        for conn in clients:
            try:conn.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:conn.close()
            except OSError:pass
        # Releasing transports also terminates UCI subprocesses.
        self.registry.stop()
        for session in sessions:
            t=session.search_thread
            if t and t is not threading.current_thread():t.join(timeout=1.)
        for t in list(self.threads):
            if t is not threading.current_thread():t.join(timeout=1.)
        telemetry('⛔', '', 'Hive global shutdown complete')

    def stdio(self):
        lock=threading.Lock()
        def emit(line):
            with lock:print(line,flush=True)
        s=Session(self,emit,'stdio')
        telemetry('🔗', '', 'UCI listening')
        with self.sessions_lock:self.sessions.add(s)
        try:
            for line in sys.stdin:
                if self.stopped.is_set():break
                if not s.command(line):break
        except (OSError,UnicodeError) as ex:LOG.warning('STDIO closed: %s',ex)
        finally:
            s.close()
            with self.sessions_lock:self.sessions.discard(s)
            if self.stopped.is_set():telemetry('⛔', 'stdio', 'session ended during global shutdown')
            else:telemetry('🔗', '', 'UCI session ended; TCP listening continues')

    def tcp_client(self,conn,addr):
        label=f'tcp:{addr[0]}:{addr[1]}';send_lock=threading.Lock()
        reason='session closed'
        def emit(line):
            nonlocal reason
            with send_lock:
                try:conn.sendall((line+'\n').encode('utf-8'))
                except OSError as ex:
                    reason='send failed: '+str(ex);session.close()
        session=Session(self,emit,label)
        with self.sessions_lock:
            if self.stopped.is_set():
                conn.close();return
            self.sessions.add(session)
            self.clients.add(conn)
        try:
            with conn:
                conn.settimeout(.25);conn.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1);pending=bytearray()
                while not self.stopped.is_set() and not session.closed:
                    try:data=conn.recv(4096)
                    except socket.timeout:continue
                    if not data:reason='peer EOF';break
                    pending.extend(data)
                    if len(pending)>1024*1024:raise ValueError('UCI input too long')
                    while b'\n' in pending:
                        raw,_,pending=pending.partition(b'\n')
                        line=raw.decode('utf-8','replace').strip()
                        if not line:continue
                        if line=='uci (master)':
                            with self.sessions_lock:
                                if getattr(session,'identified',False) or self.cfg.get('master') or self.master_session is not None:
                                    telemetry('⚠️','Hive','MULTIPLE MASTERS DETECTED or invalid master handshake')
                                    reason='master connection rejected';telemetry('❌',label,reason);return
                                self.master_session=session
                            telemetry('✅',label,'master connection accepted')
                        session.identified=True
                        if not session.command(line):
                            reason='client quit' if line=='quit' else 'command rejected'
                            return
        except (OSError,ValueError) as ex:
            reason=str(ex)
            if self.stopped.is_set():LOG.debug('TCP %s closed by Hive shutdown: %s',label,ex)
            else:LOG.warning('TCP %s disconnected: %s',label,ex)
        finally:
            session.close()
            # Keep ownership until the previous master's search has drained.
            if self.master_session is session:
                if session.search_thread:session.search_thread.join()
                for worker in session.workers:worker.join()
            with self.sessions_lock:
                if self.master_session is session:
                    self.master_session=None
                    telemetry('🔗',label,'master connection released')
                    if self.discovery:self.discovery.changed.set()
                self.sessions.discard(session)
                self.clients.discard(conn)
            telemetry('🔌',label,'TCP disconnected reason='+reason)
            LOG.info('TCP session ended %s reason=%s',label,reason)

    def accept(self):
        srv=socket.socket();self.server=srv
        srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        srv.bind((self.cfg['listen_ip'],int(self.cfg['tcp_port'])));srv.listen(16);srv.settimeout(.25)
        telemetry('🌐', '', f'TCP listening {self.cfg["listen_ip"]}:{self.cfg["tcp_port"]}')
        if self.discovery and self.cfg['broadcast']:
            t=threading.Thread(target=self.discovery.run,daemon=True);t.start();self.threads.append(t)
        try:
            while not self.stopped.is_set():
                try:c,addr=srv.accept()
                except socket.timeout:continue
                except OSError:break
                t=threading.Thread(target=self.tcp_client,args=(c,addr),daemon=True)
                t.start();self.threads.append(t)
        finally:
            try:srv.close()
            except OSError:pass

    def run(self):
        try:self.registry.startup()
        except Exception:
            self.shutdown();raise
        discovery=Discovery(self.cfg,self.registry,self.node_id)
        self.discovery=discovery
        t=threading.Thread(target=self.registry.maintain,daemon=True);t.start();self.threads.append(t)
        t=threading.Thread(target=self.stdio,daemon=True);t.start();self.threads.append(t)
        try:self.accept()
        except KeyboardInterrupt:telemetry('⛔', '', 'Ctrl+C: stopping entire Hive')
        finally:self.shutdown()


def verbosity_level(value):
    # Legacy YAML booleans map naturally to levels 0 and 1.
    if isinstance(value, bool): return int(value)
    if isinstance(value, int) and value in (0,1,2): return value
    if isinstance(value, str) and value in ('0','1','2'): return int(value)
    raise ValueError('verbose must be 0, 1 or 2')


def load_config(path):
    p=Path(path)
    if not p.is_file():raise ValueError('configuration not found: '+str(p))
    c=yaml.safe_load(p.read_text(encoding='utf-8'))
    if not isinstance(c,dict):raise ValueError('configuration must be YAML mapping')
    defaults=dict(name='Hive',node_id='',listen_ip='0.0.0.0',tcp_port=6250,udp_port=6251,
        broadcast=5,master=False,hive_network=False,broadcast_seconds=5,retry_seconds=5,
        connect_timeout_s=3,handshake_timeout_s=5,search_grace_s=1.5,max_hive_probe_jobs=32,
        depth=8,qdepth=2,timeout_ms=15000,verbose=1,recalibration_min=30,recalibration_max=60,
        test=dict(fen=chess.STARTING_FEN,move='e2e4',depth=3,qdepth=2,movetime_ms=3000),engines=[])
    defaults.update(c)
    defaults['verbose']=verbosity_level(defaults['verbose'])
    if not isinstance(defaults['master'],bool):raise ValueError('master must be boolean')
    v=defaults['broadcast']
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:
        raise ValueError('broadcast must be a positive interval in minutes (not boolean)')
    if 'broadcast_port' in c:defaults['udp_port']=c['broadcast_port']
    if not isinstance(defaults['engines'],list):raise ValueError('engines must be a list')
    names=set()
    def validate_engine(e,names,member=False):
        if isinstance(e,dict):
            e['type']=str(e.get('type','')).lower()
            if e['type']=='tcp' and not e.get('host') and e.get('ip'):e['host']=e['ip']
        if not isinstance(e,dict) or e.get('type') not in (('tcp','uci') if member else ('tcp','uci','team')) or not isinstance(e.get('name'),str) or not e['name']:
            raise ValueError('engine needs name and valid type tcp|uci|team (no nested teams)')
        if e['name'] in names:raise ValueError('duplicate engine name: '+e['name'])
        names.add(e['name'])
        if e['type']=='team':
            members=e.get('members')
            if not isinstance(members,list) or len(members)<2:raise ValueError('team '+e['name']+' requires at least two members')
            member_names=set()
            for m in members:
                validate_engine(m,member_names,True)
                w=m.get('reliability')
                if isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or not 0<=w<=1:
                    raise ValueError('team '+e['name']+' invalid member reliability')
            total=math.fsum(m['reliability'] for m in members)
            if abs(total-1)>1e-9:raise ValueError(f'team {e["name"]} sum(reliability)={total:.12g}; must equal 1')
            if e.get('fusion','mean')!='mean':raise ValueError('only mean fusion is supported')
        if e['type']=='tcp' and (not e.get('host') or not 1<=int(e.get('port',0))<=65535):
            raise ValueError('tcp engine requires host and port')
        if e['type']=='uci' and not e.get('path'):raise ValueError('uci engine requires path')
        core=e.get('core',0)
        if isinstance(core,bool) or not isinstance(core,int) or core<0:
            raise ValueError('engine '+e['name']+' core must be a nonnegative integer')
        e['core']=core
        for key,default in (('kmin',0.0),('kmax',1.0)):
            v=e.get(key,default)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1:
                raise ValueError('engine '+e['name']+' '+key+' must be numeric in [0,1]')
            e[key]=float(v)
        if not e['kmin']<e['kmax']:raise ValueError('engine '+e['name']+' requires kmin < kmax')
        options=e.get('options',{})
        if not isinstance(options,dict):raise ValueError('engine '+e['name']+' options must be mapping')
        for option,value in options.items():
            if not isinstance(option,str) or not option.strip() or any(x in option for x in '\r\n') or isinstance(value,(dict,list)) or any(x in str(value) for x in '\r\n'):
                raise ValueError('invalid UCI option on engine '+e['name'])
    for e in defaults['engines']:validate_engine(e,names)
    configured_kmin=sum(e.get('kmin',0.0) for e in defaults['engines'])
    if configured_kmin>1.0+1e-9:
        raise ValueError('sum of engine kmin must be <= 1; got '+format(configured_kmin,'.9g'))
    configured_kmax=math.fsum(e['kmax'] for e in defaults['engines'])
    if configured_kmax<1-1e-9:raise ValueError('sum of engine kmax must be >= 1; got '+format(configured_kmax,'.9g'))
    for key in ('recalibration_min','recalibration_max'):
        v=defaults[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (v<=0 and not (key=='recalibration_max' and v==-1)):raise ValueError('invalid '+key)
    if defaults['recalibration_max']!=-1 and defaults['recalibration_min']>defaults['recalibration_max']:raise ValueError('recalibration_min must be <= recalibration_max')
    for key in ('tcp_port','udp_port'):
        if not 1<=int(defaults[key])<=65535:raise ValueError('invalid '+key)
    for key in ('depth','timeout_ms','retry_seconds','connect_timeout_s','handshake_timeout_s','broadcast_seconds'):
        if float(defaults[key])<=0:raise ValueError('invalid '+key)
    if int(defaults['qdepth'])<0:raise ValueError('invalid qdepth')
    if not 1<=int(defaults['max_hive_probe_jobs'])<=128:raise ValueError('invalid max_hive_probe_jobs')
    if not isinstance(defaults['test'],dict):raise ValueError('test must be mapping')
    for key in ('fen','move','depth','movetime_ms'):
        if key not in defaults['test']:raise ValueError('test missing '+key)
    if 'qdepth' not in defaults['test']:defaults['test']['qdepth']=None
    if not defaults['node_id']:
        # Stable across restarts only if specified in the YAML; recommended.
        defaults['node_id']=uuid.uuid4().hex
    if not re.fullmatch('[0-9a-f]{32}',str(defaults['node_id'])):raise ValueError('node_id must be 32 hex digits')
    return defaults


def main(argv=None):
    ap=argparse.ArgumentParser(description='Hive recursive UCI concentrator')
    ap.add_argument('--hive',default='hive.yml',help='YAML configuration; default ./hive.yml')
    ap.add_argument('--verbose',type=int,choices=(0,1,2),default=None,help='0: client UCI; 1: summaries (default); 2: all')
    args=ap.parse_args(argv)
    try:cfg=load_config(args.hive)
    except Exception as ex:
        sys.stderr.write('⛔ Hive configuration ERROR: '+str(ex)+'\n');return 2
    global _TELEMETRY_VERBOSE, _TELEMETRY_WIDTH
    _TELEMETRY_VERBOSE=cfg['verbose'] if args.verbose is None else args.verbose
    cfg['verbose']=_TELEMETRY_VERBOSE
    _TELEMETRY_WIDTH=max([12]+[len(str(e['name'])) for e in cfg['engines']])
    logging.basicConfig(level=(logging.CRITICAL+1 if _TELEMETRY_VERBOSE==0 else logging.WARNING if _TELEMETRY_VERBOSE==1 else logging.DEBUG),
        format='⛔[%(asctime)s] %(message)s',datefmt='%H:%M:%S',stream=sys.stderr)
    telemetry('⚙️', 'Hive', f'v{VERSION} verbose={_TELEMETRY_VERBOSE} {Path(__file__).resolve()}')
    try:Hive(cfg).run();return 0
    except Exception:
        LOG.exception('fatal Hive error');return 1


if __name__=='__main__':raise SystemExit(main())
