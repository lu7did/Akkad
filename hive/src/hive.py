#!/usr/bin/env python3
"""Hive v0.2.13 - dual-front-end UCI concentrator, persistent UCI workers.

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

try:
    import yaml
    import chess
except ImportError as exc:
    sys.stderr.write(f'Hive: dependency missing: {exc}; install requirements.txt\n')
    raise SystemExit(2)

VERSION = '0.2.13'
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


def telemetry_priority(registry):
    """Print equilibrium only when connected-set or effective shares change."""
    ready = [e for e in registry.snapshot()
             if e.transport is not None and not e.transport.dead.is_set()]
    values = tuple(sorted((e.name, round(e.priority, 8)) for e in ready))
    with registry.lock:
        if values == registry.last_equilibrium:
            return
        registry.last_equilibrium = values
    for name, share in values:
        telemetry('⚖️', name, f'{share:.5f}')
    if not values:
        telemetry('⚖️', '', 'no connected engines')
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


class Transport:
    def __init__(self, spec, timeout):
        self.name = spec['name']
        self.proc=None;self.sock=None;self.reader=None;self.writer=None
        self.timeout=timeout;self.q=queue.Queue();self.dead=threading.Event()
        self.stderr_tail=deque(maxlen=24);self.stderr_lock=threading.Lock()
        if spec['type']=='tcp':
            self.sock=socket.create_connection((spec['host'],int(spec['port'])),timeout)
            self.sock.settimeout(.25)
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
                try:self.proc.kill()
                except OSError:pass
            for f in (self.proc.stdin,self.proc.stdout,self.proc.stderr):
                try:f.close()
                except (OSError,ValueError):pass


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
        self.last_test_ms=None;self.test_nps=0;self.k=0.0;self.priority=0.0;self.probe_count=1
        self.kmin=spec.get('kmin')
        self.remote_id=None;self.support_qdepth=False
        self.next_retry=0.0;self.last_seen=time.monotonic();self.connecting=False;self.attempted=False;self.reserved=False

    def available(self):
        with self.lock:return self.transport is not None and not self.busy and not self.transport.dead.is_set()

    def connect(self,config,self_id):
        with self.lock:
            if self.transport is not None or self.connecting:return False
            self.connecting=True;self.attempted=True
            trans=None
            try:
                trans=Transport(self.spec,float(config['connect_timeout_s']))
                trans.send('uci');handshake=trans.until('uciok',float(config['handshake_timeout_s']))
                for line in handshake:
                    if line.startswith('option name HiveNodeID '):
                        self.remote_id=line.split(' default ',1)[-1].strip()
                    if line.startswith('option name QDepth '):self.support_qdepth=True
                # A strictly descending order of Hive IDs makes directed cycles impossible,
                # including simultaneous discoveries and statically configured Hive links.
                if self.spec.get('discovered_id') and self.remote_id!=self.spec['discovered_id']:
                    raise ValueError('discovery node ID differs from UCI handshake ID')
                if self.remote_id:
                    if self.remote_id==self_id or self_id<=self.remote_id:
                        raise ValueError('Hive-to-Hive cycle guard: requires parent id > child id')
                # Engine-specific UCI options, e.g. Stockfish Threads/Hash.
                # These are protocol commands, not executable CLI arguments.
                for key,value in self.spec.get('options',{}).items():
                    trans.send(f'setoption name {key} value {value}')
                trans.send('isready');trans.until('readyok',float(config['handshake_timeout_s']))
                self.transport=trans
                telemetry('✅', self.name, f'connected type={self.spec["type"]} remote_id={self.remote_id}')
                return True
            except Exception as ex:
                telemetry('⛔', self.name, f'error while connecting: {ex}')
                LOG.warning('CONNECT ERROR %s: %s',self.name,ex)
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
            while True:
                line=t.recv(deadline,cancel)
                if line.startswith('info '):
                    if line.startswith('info string ERROR'):
                        engine_errors.append(line)
                        LOG.warning('ENGINE %s: %s',self.name,line)
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
            if best not in moves:
                detail=('; '.join(engine_errors[-3:]) if engine_errors else 'no error detail from engine')
                raise ValueError('bestmove outside assigned searchmoves: '+str(best)+'; '+detail)
            if best not in infos and recent and len(moves)==1 and numeric_score(recent) is not None:
                infos[best]=dict(recent,move=best)
            if best not in infos:raise ValueError('bestmove without usable UCI score')
            inf=infos[best]
            score=f'mate {inf["mate"]}' if inf['mate'] is not None else f'cp {inf["cp"]}'
            bound='' if inf['bound']=='exact' else ' '+inf['bound']
            telemetry('🧠', self.name, f'{line} score {score}{bound} depth {inf["depth"] if inf["depth"] is not None else "?"} nodes {last_nodes} time {last_time if last_time is not None else "?"} nps {last_nps}')
            return WorkResult(self.name,best,infos,round((time.monotonic()-started)*1000),last_nps,last_nodes,last_time,last_simulations)
        except Exception:
            # Flush/discard an interrupted transaction; otherwise late bestmove
            # could be mistaken for the next request.
            self.drop();raise
        finally:
            with self.lock:self.busy=False


class Registry:
    def __init__(self,config,node_id):
        self.config=config;self.node_id=node_id;self.lock=threading.RLock()
        self.items={e['name']:Endpoint(e) for e in config['engines']}
        self.clone_sequence=0
        self.last_equilibrium=None
        self.stopped=threading.Event();self.monitor=None;self.discover_pending=set()

    def snapshot(self):
        with self.lock:return list(self.items.values())

    def active(self):return [x for x in self.snapshot() if x.available() and not x.reserved]

    def claim(self):
        # Atomic choice against concurrent UCI frontend sessions.
        with self.lock:
            result=[]
            for ep in self.items.values():
                with ep.lock:
                    if ep.transport is not None and not ep.busy and not ep.reserved and not ep.transport.dead.is_set():
                        ep.reserved=True;result.append(ep)
            return result

    def release(self,ep):
        with ep.lock:ep.reserved=False

    def has_connected_busy(self):
        with self.lock:
            return any(e.transport is not None and not e.transport.dead.is_set() and
                       (e.busy or e.reserved) for e in self.items.values())

    def spawn_local_if_needed(self):
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
            spec.pop('kmin',None)
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
        """Effective task probabilities for the *eligible* endpoint set.

        Explicit kmin is a reserved probability (not a performance-derived
        weight). All unconfigured endpoints share the remainder inversely
        proportional to measured probe wall time. A configuration with only
        explicit minima summing below one deliberately leaves probability
        unallocated. The assignment algorithm normalizes only for scheduling
        a finite, non-empty move list.
        """
        if not endpoints:
            return {}
        fixed=[ep for ep in endpoints if ep.kmin is not None]
        unspecified=[ep for ep in endpoints if ep.kmin is None]
        reserved=sum(float(ep.kmin) for ep in fixed)
        if reserved>1.0+1e-9:
            raise ValueError('sum of active kmin exceeds 1')
        remaining=max(0.0,1.0-reserved)
        result={ep.name:float(ep.kmin) for ep in fixed}
        if unspecified:
            times=[ep.last_test_ms for ep in unspecified]
            valid=all(isinstance(d,(int,float)) and math.isfinite(d) and d>0 for d in times)
            speeds=[1.0/float(d) for d in times] if valid else [1.0]*len(unspecified)
            total=sum(speeds)
            for ep,v in zip(unspecified,speeds):
                result[ep.name]=remaining*(v/total) if total>0 else remaining/len(unspecified)
        return result

    def weights(self):
        ready=[e for e in self.snapshot() if e.transport is not None and not e.transport.dead.is_set()]
        n=len(ready)
        if not n:
            telemetry_priority(self)
            return []
        ds=[e.last_test_ms for e in ready]
        total=sum(ds) if all(isinstance(x,(int,float)) and x>0 and math.isfinite(x) for x in ds) else 0
        for e,d in zip(ready,ds):e.k=d/total if total>0 else 1/n
        priorities=self.effective_priorities(ready)
        for ep in ready:ep.priority=priorities[ep.name]
        for e in ready:
            telemetry('⚙️', e.name,
                f'latency_k={e.k:.5f} kmin={e.kmin if e.kmin is not None else "auto"} '
                f'priority={e.priority:.5f} wall_test_ms={e.last_test_ms}; '
                f'total_priority={sum(priorities.values()):.5f}')
        telemetry_priority(self)
        return ready

    def test(self,ep):
        """Probe a leaf once or probe an advertised Hive with N parallel jobs.

        Each Hive job is a separate TCP/UCI session. This measures aggregate
        completion wall time, rather than sequentially testing one socket N times.
        """
        b=chess.Board(self.config['test']['fen']);move=self.config['test']['move']
        if chess.Move.from_uci(move) not in b.legal_moves:raise ValueError('invalid test move')
        count=max(1,int(getattr(ep,'probe_count',1))) if ep.remote_id else 1
        count=min(count,int(self.config.get('max_hive_probe_jobs',32)))
        position='position fen '+b.fen()
        telemetry('✅', ep.name, f'test FEN={b.fen()} move={move}')
        if ep.spec['type']=='uci':
            telemetry_args(ep.name, [ep.spec['path']] + shlex.split(ep.spec.get('args',''), posix=True))
        else:
            telemetry('⚙️', ep.name, f'TCP {ep.spec.get("host")}:{ep.spec.get("port")}')
        depth=int(self.config['test']['depth']);qdepth=self.config['test']['qdepth']
        budget=int(self.config['test']['movetime_ms'])
        if count==1:
            result=ep.analyze(position,[move],depth,qdepth,budget)
            ep.last_test_ms=max(1,result.elapsed_ms);ep.test_nps=max(0,result.nps)
            # Distinguish measured end-to-end wall time from the engine's UCI
            # search time. NPS is an engine-provided metric: for AlphaZero its
            # nodes are MCTS tree nodes, not alpha-beta nodes. Never imply
            # that either metric is directly comparable across algorithms.
            telemetry('⚙️', ep.name,
                      f'wall_test_ms={ep.last_test_ms} uci_time_ms={result.uci_time_ms} '
                      f'uci_nodes={result.nodes} uci_nps={ep.test_nps} '
                      f'mcts_simulations={result.simulations} cp={result.infos[result.best].get("cp")}')
            LOG.info('TEST %s jobs=1 wall_ms=%s uci_time_ms=%s '
                     'uci_nodes=%s uci_nps=%s mcts_simulations=%s cp=%s '
                     'depth_requested=%s movetime_requested_ms=%s',
                     ep.name,ep.last_test_ms,result.uci_time_ms,result.nodes,
                     ep.test_nps,result.simulations,result.infos[result.best].get('cp'),
                     depth,budget)
            return
        # A connected Hive cannot handle simultaneous UCI searches on one
        # session/socket. Open distinct temporary TCP clients for parallel probes.
        # All requests share the original position and limits.
        started=time.monotonic();out=queue.Queue();threads=[]
        def one(index):
            peer=None
            try:
                if index==0:
                    result=ep.analyze(position,[move],depth,qdepth,budget)
                else:
                    peer=Endpoint(dict(ep.spec,name=ep.name+'#probe-'+str(index)),static=False)
                    if not peer.connect(self.config,self.node_id):raise ConnectionError('probe TCP connection refused')
                    result=peer.analyze(position,[move],depth,qdepth,budget)
                out.put(result)
            except Exception as exc:out.put(exc)
            finally:
                if peer:peer.drop()
        for i in range(count):
            t=threading.Thread(target=one,args=(i,),daemon=True,name='probe-'+ep.name+'-'+str(i));t.start();threads.append(t)
        for t in threads:t.join(timeout=budget/1000+2*float(self.config['connect_timeout_s'])+
                                  2*float(self.config['handshake_timeout_s']))
        responses=[out.get_nowait() for _ in range(out.qsize())]
        completed=[r for r in responses if isinstance(r,WorkResult)]
        if len(completed)!=count:
            raise RuntimeError('incomplete parallel Hive probe '+str(len(completed))+'/'+str(count))
        # Equivalent latency per single move for capacity scheduling:
        # aggregate makespan / successful concurrent jobs.
        wall_ms=max(1,round((time.monotonic()-started)*1000))
        ep.last_test_ms=max(1,wall_ms/count)
        ep.test_nps=sum(max(0,r.nps) for r in completed)
        telemetry('⚙️', ep.name, f'probe_jobs={count} wall_ms={wall_ms} effective_ms_per_move={ep.last_test_ms:.2f} nps={ep.test_nps}')
        LOG.info('TEST HIVE %s jobs=%s wall_ms=%s effective_ms_per_move=%.2f nps=%s',
                 ep.name,count,wall_ms,ep.last_test_ms,ep.test_nps)

    def _connect_and_test(self,ep):
        with ep.lock:ep.reserved=True
        if ep.connect(self.config,self.node_id):
            try:self.test(ep)
            except Exception as ex:
                telemetry('⛔', ep.name, f'test failed: {ex}')
                LOG.warning('TEST FAILED %s: %s',ep.name,ex);ep.drop()
            finally:
                with ep.lock:ep.reserved=False
                self.weights()
        else:
            with ep.lock:ep.reserved=False

    def maintain(self):
        while not self.stopped.is_set():
            now=time.monotonic()
            for ep in self.snapshot():
                if self.stopped.is_set():break
                if ep.transport and ep.transport.dead.is_set():
                    ep.drop();self.weights()
                if ep.transport is None and ep.static and not ep.connecting and now>=ep.next_retry and (ep.spec['type']=='tcp' or not ep.attempted):
                    ep.next_retry=now+float(self.config['retry_seconds'])
                    self._connect_and_test(ep)
            self.stopped.wait(.3)

    def discovered(self,advert):
        if advert.get('node_id')==self.node_id:return
        their_id=advert.get('node_id','')
        if not isinstance(their_id,str) or not re.fullmatch('[0-9a-f]{32}',their_id):return
        # Strict ordering: every network edge must point from high to low id.
        if self.node_id<=their_id:return
        host=advert.get('ip');port=advert.get('port')
        if not isinstance(host,str) or not isinstance(port,int) or not 1<=port<=65535:return
        try:socket.inet_aton(host)
        except OSError:return
        name='discovered-'+their_id
        with self.lock:
            if name in self.items:
                ep=self.items[name]
                if ep.available():return
                # Dynamic peers are only retried upon a fresh advertisement.
                if ep.busy or ep.connecting:return
                ep.spec.update(host=host,port=port)
                ep.probe_count=max(1,int(advert.get('engines',1))) if isinstance(advert.get('engines'),int) else 1
            else:
                ep=Endpoint(dict(name=name,type='tcp',host=host,port=port,discovered_id=their_id),static=False)
                ep.probe_count=max(1,int(advert.get('engines',1))) if isinstance(advert.get('engines'),int) else 1
                self.items[name]=ep
        with self.lock:
            if ep.transport is not None or ep.connecting or name in self.discover_pending:return
            self.discover_pending.add(name)
        def connect_once():
            try:self._connect_and_test(ep)
            finally:
                with self.lock:self.discover_pending.discard(name)
        threading.Thread(target=connect_once,daemon=True).start()

    def stop(self):
        self.stopped.set()
        for ep in self.snapshot():ep.drop()


class Discovery:
    def __init__(self,config,registry,node_id):
        self.cfg=config;self.registry=registry;self.node_id=node_id
        self.stop=threading.Event();self.sock=None

    def local_ip(self):
        bind=self.cfg.get('advertise_ip')
        if bind:return bind
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:s.connect(('192.0.2.1',9));return s.getsockname()[0]
        except OSError:return '127.0.0.1'
        finally:s.close()

    def announce(self):
        payload=dict(kind='HIVE_ADVERTISE',node_id=self.node_id,name=self.cfg['name'],
           ip=self.local_ip(),port=int(self.cfg['tcp_port']),
           engines=sum(1 for e in self.registry.snapshot() if e.transport is not None and not e.transport.dead.is_set()),
           nps=sum(e.test_nps for e in self.registry.snapshot() if e.transport is not None and not e.transport.dead.is_set()))
        return json.dumps(payload,separators=(',',':')).encode('utf-8')

    def run(self):
        # SO_REUSEADDR permits multiple Hives to listen for broadcasts on one LAN host.
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock=s
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            s.bind(('',int(self.cfg['udp_port'])));s.settimeout(.25)
            tx=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);tx.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
            try:
                next_tx=0
                while not self.stop.is_set():
                    if self.cfg['broadcast'] and time.monotonic()>=next_tx:
                        try:
                            payload=self.announce()
                            tx.sendto(payload,('255.255.255.255',int(self.cfg['udp_port'])))
                            telemetry('🚨', '', payload.decode('utf-8','replace'))
                        except OSError as ex:LOG.warning('BROADCAST: %s',ex)
                        next_tx=time.monotonic()+float(self.cfg['broadcast_seconds'])
                    try:data,_=s.recvfrom(2048)
                    except socket.timeout:continue
                    except OSError:
                        if self.stop.is_set():break
                        raise
                    if not self.cfg['hive_network']:continue
                    try:
                        advert=json.loads(data.decode('utf-8'))
                        if advert.get('kind')=='HIVE_ADVERTISE':self.registry.discovered(advert)
                    except (ValueError,UnicodeError,AttributeError):continue
            finally:tx.close()
        finally:s.close()


class Session:
    def __init__(self,hive,emit,label):
        self.hive=hive;self.emit=emit;self.label=label
        self.board=chess.Board();self.position='position startpos'
        self.stop=threading.Event();self.search_thread=None
        self.search_lock=threading.Lock();self.closed=False

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
            self.stop.clear()
            if not moves:self.send('bestmove 0000');return
            t=threading.Thread(target=self._search,args=(self.position,moves,depth,qdepth,budget,clock_deadline),daemon=True)
            self.search_thread=t;t.start()

    def _search(self,position,moves,depth,qdepth,budget,clock_deadline=None):
        start=time.monotonic();eps=[]
        # Reservation is per UCI session. Never place work on busy endpoints.
        # TCP-only contention waits for resources even beyond the UCI movetime;
        # the actual search budget begins once a resource is acquired.
        # Local UCI engines can be replicated into independent processes.
        while not self.stop.is_set() and not self.hive.stopped.is_set() and not self.closed:
            if clock_deadline is not None and time.monotonic()>=clock_deadline:break
            eps=self.hive.registry.claim()
            if eps:break
            if any(e.static and e.spec['type']=='uci' for e in self.hive.registry.snapshot()):
                ep=self.hive.registry.spawn_local_if_needed()
                if ep:
                    eps=self.hive.registry.claim()
                    if eps:break
            if not self.hive.registry.has_connected_busy():
                self.send('info string Hive no connected engines');self.send('bestmove 0000');return
            time.sleep(.025)
        if not eps:
            self.send('info string Hive search cancelled while waiting for an engine');self.send('bestmove 0000');return
        # Waiting for a busy TCP engine is outside the requested thinking budget.
        search_start=time.monotonic()
        if clock_deadline is not None:
            budget=min(budget,max(1,int((clock_deadline-search_start)*1000)))
        # The specified k=delta/sum(delta) grows for slow engines; to allocate
        # more work to faster engines use reciprocal k, never k directly.
        # Refresh preference indices from all currently connected clients,
        # including the claimed endpoints (do not hide them as busy).
        connected=[e for e in self.hive.registry.snapshot() if e.transport and e.last_test_ms]
        total=sum(e.last_test_ms for e in connected)
        if total>0:
            for e in connected:e.k=e.last_test_ms/total
        # A session uses only currently reserved endpoints; disconnected or
        # busy endpoints cannot consume a share of this search's tasks.
        weights=self.hive.registry.effective_priorities(eps)
        buckets={e.name:[] for e in eps}
        # The shares are probabilities, not a requirement that each endpoint
        # receive at least one task when the move count is small. A zero-share
        # endpoint receives no work; all assigned tasks are still distributed.
        eligible=[e for e in eps if weights[e.name]>0]
        if not eligible:
            # Degenerate legal configuration: every explicit kmin is zero.
            # Use even fallback solely to avoid discarding legal root moves.
            eligible=eps
            weights={e.name:1.0/len(eps) for e in eps}
        for m in moves:
            e=min(eligible,key=lambda x:(len(buckets[x.name])+1)/weights[x.name])
            buckets[e.name].append(m)
        work=[(e,buckets[e.name]) for e in eps if buckets[e.name]]
        for e in eps:
            if not buckets[e.name]:self.hive.registry.release(e)
        telemetry('⚙️', self.label, 'assigned '+str(sum(len(ms) for _,ms in work))+'/'+str(len(moves))+' '+ ' '.join(f'{e.name}={len(ms)} ({weights[e.name]:.3f})' for e,ms in work))
        replies=queue.Queue()
        def run(ep,assigned):
            try:r=ep.analyze(position,assigned,depth,qdepth,budget,self.stop);replies.put(r)
            except Exception as ex:LOG.warning('WORK %s failed %s',ep.name,ex);replies.put(None)
            finally:self.hive.registry.release(ep)
        for ep,assigned in work:threading.Thread(target=run,args=(ep,assigned),daemon=True).start()
        pending=len(work);results=[];deadline=search_start+budget/1000+float(self.hive.cfg['search_grace_s'])
        if clock_deadline is not None:deadline=min(deadline,clock_deadline)
        while pending and not self.stop.is_set() and time.monotonic()<deadline:
            try:r=replies.get(timeout=min(.1,max(.01,deadline-time.monotonic())))
            except queue.Empty:continue
            pending-=1
            if r:results.append(r)
        if pending or self.stop.is_set():
            for ep,_ in work:
                if ep.busy:ep.drop()
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
                self.send('id name Hive '+str(self.hive.cfg['name']))
                self.send('id author Akkad')
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
        def emit(line):
            with send_lock:
                try:conn.sendall((line+'\n').encode('utf-8'))
                except OSError:session.close()
        session=Session(self,emit,label)
        with self.sessions_lock:
            if self.stopped.is_set():
                conn.close();return
            self.sessions.add(session)
            self.clients.add(conn)
        try:
            with conn:
                conn.settimeout(.25);pending=bytearray()
                while not self.stopped.is_set() and not session.closed:
                    try:data=conn.recv(4096)
                    except socket.timeout:continue
                    if not data:break
                    pending.extend(data)
                    if len(pending)>1024*1024:raise ValueError('UCI input too long')
                    while b'\n' in pending:
                        raw,_,pending=pending.partition(b'\n')
                        if not session.command(raw.decode('utf-8','replace').strip()):return
        except (OSError,ValueError) as ex:
            if self.stopped.is_set():LOG.debug('TCP %s closed by Hive shutdown: %s',label,ex)
            else:LOG.warning('TCP %s disconnected: %s',label,ex)
        finally:
            session.close()
            with self.sessions_lock:
                self.sessions.discard(session)
                self.clients.discard(conn)
            LOG.info('TCP session ended %s',label)

    def accept(self):
        srv=socket.socket();self.server=srv
        srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        srv.bind((self.cfg['listen_ip'],int(self.cfg['tcp_port'])));srv.listen(16);srv.settimeout(.25)
        telemetry('🌐', '', f'TCP listening {self.cfg["listen_ip"]}:{self.cfg["tcp_port"]}')
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
        discovery=Discovery(self.cfg,self.registry,self.node_id)
        self.discovery=discovery
        t=threading.Thread(target=self.registry.maintain,daemon=True);t.start();self.threads.append(t)
        if self.cfg['broadcast'] or self.cfg['hive_network']:
            t=threading.Thread(target=discovery.run,daemon=True);t.start();self.threads.append(t)
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
        broadcast=False,hive_network=False,broadcast_seconds=5,retry_seconds=5,
        connect_timeout_s=3,handshake_timeout_s=5,search_grace_s=1.5,max_hive_probe_jobs=32,
        depth=8,qdepth=2,timeout_ms=15000,verbose=1,
        test=dict(fen=chess.STARTING_FEN,move='e2e4',depth=3,qdepth=2,movetime_ms=3000),engines=[])
    defaults.update(c)
    defaults['verbose']=verbosity_level(defaults['verbose'])
    if not isinstance(defaults['engines'],list):raise ValueError('engines must be a list')
    names=set()
    for e in defaults['engines']:
        if isinstance(e,dict):
            e['type']=str(e.get('type','')).lower()
            if e['type']=='tcp' and not e.get('host') and e.get('ip'):e['host']=e['ip']
        if not isinstance(e,dict) or e.get('type') not in ('tcp','uci') or not isinstance(e.get('name'),str) or not e['name']:
            raise ValueError('engine needs name and type tcp|uci')
        if e['name'] in names:raise ValueError('duplicate engine name: '+e['name'])
        names.add(e['name'])
        if e['type']=='tcp' and (not e.get('host') or not 1<=int(e.get('port',0))<=65535):
            raise ValueError('tcp engine requires host and port')
        if e['type']=='uci' and not e.get('path'):raise ValueError('uci engine requires path')
        if 'kmin' in e:
            v=e['kmin']
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0.0<=v<=1.0:
                raise ValueError('engine '+e['name']+' kmin must be numeric in [0,1]')
            e['kmin']=float(v)
        options=e.get('options',{})
        if not isinstance(options,dict):raise ValueError('engine '+e['name']+' options must be mapping')
        for option,value in options.items():
            if not isinstance(option,str) or not option.strip() or any(x in option for x in '\r\n') or isinstance(value,(dict,list)) or any(x in str(value) for x in '\r\n'):
                raise ValueError('invalid UCI option on engine '+e['name'])
    configured_kmin=sum(e.get('kmin',0.0) for e in defaults['engines'])
    if configured_kmin>1.0+1e-9:
        raise ValueError('sum of engine kmin must be <= 1; got '+format(configured_kmin,'.9g'))
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
        sys.stderr.write('Hive configuration ERROR: '+str(ex)+'\n');return 2
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
