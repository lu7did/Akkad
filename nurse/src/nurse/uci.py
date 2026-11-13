"""Nurse orchestrator: one UCI frontend; three persistent backend types."""
import argparse,sys,threading,time,json,shlex,os
from pathlib import Path
from . import __version__
from .config import read_brain,read_brains,brain_fingerprint
from .transport import Transport,TransportError
from .telemetry import log

class Nurse:
    def __init__(self,brains,ident,out=None):
        self.brains=Path(brains).resolve();self.ident=ident
        self.cfg=read_brain(self.brains,ident)
        self.out=out if out is not None else sys.stdout
        self._outlock=threading.Lock();self._state_lock=threading.RLock()
        self.transport=None;self.position='position startpos';self.search=None
        self.started=False;self.closed=False;self.options={};self._pending_uci_options=[]
        self.timeout=self.cfg['timeout']/1000
        self.tmax=self.cfg['tmax']
        self.retry=float(self.cfg.get('retry',5))
        self.next_retry=0.0
        log(f'💻 sargon-nurse v{__version__} brain={ident} type={self.cfg["_type"]} ELO={self.cfg.get("ELO","n/a")} tmax_ms={self.tmax} timeout_ms={self.cfg["timeout"]} warmup_movetime_ms={self.cfg["warmup_movetime"]}')
        if self.cfg['_type']=='nurse':
            log(f'⚙️ player={self.cfg["_player"]} evaluator={self.cfg["_evaluator"]} network={self.cfg.get("_network")} depth={self.cfg.get("Depth",2)} qdepth={self.cfg.get("QDepth",0)} arguments={self.cfg.get("arguments",{})}')
        elif self.cfg['_type']=='uci':log(f'⚙️ UCI engine={self.cfg["_engine"]} args={self.cfg.get("_args",[])} options={self.cfg.get("_uci_options",[])}')
        else:log(f'⚙️ TCP endpoint={self.cfg["ipaddress"]}:{self.cfg["port"]} retry_seconds={self.cfg.get("retry",5)}')
    def emit(self,line):
        with self._outlock:print(line,file=self.out,flush=True)
    def _ensure(self):
        if self.transport is not None:return
        typ=self.cfg['_type']
        if typ=='external' and time.monotonic()<self.next_retry:
            raise TransportError(f'TCP desconectado; próximo reintento en {self.next_retry-time.monotonic():.1f}s')
        t=Transport()
        t.wire_uci=(typ in ('uci','external'))
        try:
            if typ=='nurse':
                mod=self.cfg['_player'].replace('-','_')
                t.process([sys.executable,'-u','-m','nurse.players.'+mod,'--serve','--config',json.dumps(self.cfg)])
                t.send(json.dumps({'cmd':'ready'}))
                reply=json.loads(t.recv(self.timeout))
                if not reply.get('ready'):raise TransportError('worker no listo')
            elif typ=='uci':
                exe=self.cfg['_engine'];args=self.cfg.get('_args',[])
                t.process([exe]+args,cwd=str(Path(exe).parent) if Path(exe).is_absolute() else None)
                t.handshake(self.timeout,options=self.cfg.get("_uci_options",()))
                for option in self._pending_uci_options:t.send(option)
                if self._pending_uci_options:
                    t.send("isready");t.until("readyok",self.timeout)
                    self._pending_uci_options.clear()
            else:
                t.tcp(self.cfg['ipaddress'],self.cfg['port'],timeout=self.timeout)
                t.handshake(self.timeout,options=self.cfg.get("_uci_options",()))
                # UCI id name is recorded verbatim as informational telemetry.
                # Never compare it with the local brain ID or endpoint hostname.
                log(f'✅ external brain={self.ident} UCI id name={t.uci_name or "(no informado)"!r} provenance={t.provenance()!r}')
                for option in self._pending_uci_options:t.send(option)
                if self._pending_uci_options:
                    t.send("isready");t.until("readyok",self.timeout)
                    self._pending_uci_options.clear()
            self.transport=t;self.started=True
        except BaseException:
            t.close()
            if typ=='external':self.next_retry=time.monotonic()+self.retry
            raise
    def _position_fen(self):
        import chess
        tokens=shlex.split(self.position)
        if len(tokens)<2:raise ValueError('position incompleta')
        if tokens[1]=='startpos':board=chess.Board();idx=2
        elif tokens[1]=='fen':
            if len(tokens)<8:raise ValueError('FEN incompleto')
            board=chess.Board(' '.join(tokens[2:8]));idx=8
        else:raise ValueError('position inválida')
        if idx<len(tokens) and tokens[idx]=='moves':
            for uci in tokens[idx+1:]:board.push_uci(uci)
        return board.fen()
    def _emit_error(self,exc,search=False):
        log(f'❌ brain={self.ident} {type(exc).__name__}: {exc}')
        self.emit('info string nurse error '+str(exc).replace('\n',' ')[:180])
        if search:self.emit('bestmove 0000')
    def _bounded_go(self, go):
        """Honor requested search controls but never exceed tmax milliseconds.

        UCI depth-only and nodes-only searches receive a movetime ceiling.
        Time-control and infinite/ponder commands are intentionally normalized
        to finite go movetime searches; Nurse is a bounded-move orchestrator.
        """
        tokens=go.strip().split()
        if not tokens or tokens[0].lower() != 'go':
            raise ValueError('se esperaba comando UCI go')
        requested=self.tmax
        if 'movetime' in tokens:
            idx=tokens.index('movetime')
            if idx+1 >= len(tokens):raise ValueError('go movetime sin valor')
            requested=int(tokens[idx+1])
            if requested<1:raise ValueError('go movetime debe ser positivo')
        budget=min(requested,self.tmax)
        # Keep compatible deterministic limits; strip every time-control option.
        kept=['go']; i=1
        with_value={'movetime','wtime','btime','winc','binc','movestogo','depth','nodes','mate'}
        preserve={'depth','nodes','mate'}
        while i<len(tokens):
            token=tokens[i].lower()
            if token in with_value:
                if i+1>=len(tokens):raise ValueError(f'go {token} sin valor')
                if token in preserve:kept.extend([token,tokens[i+1]])
                i+=2
            elif token in ('infinite','ponder'):
                i+=1
            elif token=='searchmoves':
                # searchmoves takes a variable count of moves to end of command.
                kept.extend(tokens[i:]);break
            else:
                raise ValueError(f'parámetro go no soportado: {token}')
        # When searchmoves exists, insert movetime before it.
        if 'searchmoves' in kept:
            kept[kept.index('searchmoves'):kept.index('searchmoves')]=['movetime',str(budget)]
        else:kept+=['movetime',str(budget)]
        return ' '.join(kept),budget

    def _search_worker(self,go):
        try:
            self._ensure()
            bounded,budget=self._bounded_go(go)
            typ=self.cfg['_type']
            log(f'🔎 brain={self.ident} go={bounded!r} tmax={self.tmax}ms timeout={self.cfg["timeout"]}ms')
            if typ=='nurse':
                self.transport.send(json.dumps({'cmd':'choose','fen':self._position_fen(),'go':bounded}))
                # A slow search is not a communication timeout. Communication
                # grace begins after the configured thinking budget has elapsed.
                reply=json.loads(self.transport.recv(budget/1000+self.timeout))
                if not reply.get('ok'):raise TransportError(reply.get('error','worker error'))
                cp=reply['score_cp'] if reply.get('turn_white') else -reply['score_cp']
                info='info depth {depth} nodes {nodes} time {time} nps {nps} score cp '.format(**reply)+str(cp)
                if 'simulations' in reply:
                    self.emit('info string MCTSP simulations={simulations} nodes={nodes} time={time} value={value:.6f} visits={visits} stop={stop_reason}'.format(**reply))
                self.emit(info);self.emit('bestmove '+reply['bestmove'])
            else:
                if typ=='external':
                    log(f'🔎 external brain={self.ident} search_socket={self.transport.provenance()!r}')
                self.transport.send(self.position)
                self.transport.send(bounded)
                # Overall watchdog = thinking budget + communication grace.
                deadline=time.monotonic()+budget/1000+self.timeout
                while True:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError(f'bestmove excedió tmax={budget}ms + timeout={self.cfg["timeout"]}ms')
                    line=self.transport.recv(remaining)
                    if line.startswith('info ') or line.startswith('bestmove '):self.emit(line)
                    if line.startswith('bestmove '):break
        except (TransportError,TimeoutError,ValueError,OSError,json.JSONDecodeError) as exc:
            self._emit_error(exc,search=True)
            self._drop_transport()
        finally:
            with self._state_lock:self.search=None
    def _drop_transport(self):
        t=self.transport;self.transport=None
        if t:
            t.close()
            if self.cfg['_type']=='external':
                self.next_retry=time.monotonic()+self.retry
                log(f'🔄 TCP próxima reconexión en {self.retry:g}s')
    def _reconnect_loop(self):
        while not self.closed:
            if self.started and self.transport is None and self.cfg['_type']=='external':
                if time.monotonic()>=self.next_retry:
                    try:
                        self._ensure()
                        log('✅ TCP reconectado; enviar nueva posición antes de buscar')
                    except (TransportError,TimeoutError,OSError) as exc:
                        log(f'🔄 TCP reintento fallido: {exc}')
            time.sleep(.2)
    def dispatch(self,line):
        if not line:return True
        cmd=line.split(None,1)[0].lower()
        if cmd=='uci':
            if self.cfg['_type']=='external':
                # A TCP profile must not claim UCI readiness if no remote
                # engine has completed the real UCI handshake.
                try:self._ensure()
                except (TransportError,TimeoutError,OSError) as exc:
                    self._emit_error(exc)
                    return False
            # Explicit engine provenance inside the legal UCI identity message.
            # Benchmark refuses an outdated or wrong backend instead of trusting
            # superficially plausible moves/nodes.
            remote = self.transport.uci_name if self.cfg['_type']=='external' and self.transport else None
            identity=f'Sargon Nurse {self.ident} v{__version__} backend={self.cfg["_type"]}'
            if remote:identity+=f' remote={remote}'
            # The benchmark receives one diagnostic UCI info string, extracted
            # from the live TCP socket. The remote UCI name is information only.
            if self.cfg['_type']=='external':
                details=self.transport.provenance()
                self.emit('info string nurse_external_provenance '+json.dumps(details,ensure_ascii=True,separators=(',',':')))
            self.emit('id name '+identity)
            self.emit('id author Akkad')
            self.emit('uciok')
        elif cmd=='isready':
            try:self._ensure();self.emit('readyok')
            except Exception as e:self._emit_error(e)
        elif cmd=='ucinewgame':
            self.position='position startpos'
            if self.transport and self.cfg['_type']!='nurse':
                try:self.transport.send('ucinewgame')
                except TransportError:self._drop_transport()
        elif cmd=='position':self.position=line
        elif cmd=='setoption':
            # Forward options only to UCI backends, preserve original spelling.
            if self.cfg['_type']!='nurse':
                if self.transport:self.transport.send(line)
                else:self._pending_uci_options.append(line)
        elif cmd=='go':
            with self._state_lock:
                if self.search and self.search.is_alive():
                    self.emit('info string nurse busy: search in progress')
                    return True
                self.search=threading.Thread(target=self._search_worker,args=(line,),daemon=True)
                self.search.start()
        elif cmd=='stop':
            if self.transport and self.cfg['_type']!='nurse':
                try:self.transport.send('stop')
                except TransportError:self._drop_transport()
            else:log('⚠️ stop de player Python no es preemptivo; espera búsqueda en curso')
        elif cmd=='ponderhit':
            if self.transport and self.cfg['_type']!='nurse':self.transport.send('ponderhit')
        elif cmd=='quit':return False
        else:self.emit('info string nurse comando desconocido '+cmd)
        return True
    def run(self,input_stream=None):
        if self.cfg['_type']=='external':
            threading.Thread(target=self._reconnect_loop,daemon=True).start()
        try:
            for line in input_stream if input_stream is not None else sys.stdin:
                if not self.dispatch(line.strip()):break
        finally:
            self.closed=True
            active_search=self.search
            if active_search and active_search.is_alive():
                if self.transport and self.cfg['_type']!='nurse':
                    try:self.transport.send('stop')
                    except TransportError:pass
                active_search.join(timeout=3)
            self._drop_transport()
        return 0

def main(argv=None):
    ap=argparse.ArgumentParser(description='Sargon Nurse independent UCI engine')
    ap.add_argument('--brains',required=True,help='brains.json configuration')
    ap.add_argument('--expect-brain-sha256',help='SHA-256 de la entrada brain validada por el cliente')
    ap.add_argument('--expect-endpoint',help='Destino TCP host:port exigido por el cliente (solo external)')
    ap.add_argument('--id',required=True,help='brain identifier')
    ap.add_argument('--depth',type=int,help='override Depth')
    ap.add_argument('--qdepth',type=int,help='override QDepth')
    ap.add_argument('--timeout',type=int,help='override communication timeout in milliseconds')
    ap.add_argument('--tmax',type=int,help='override search budget in milliseconds')
    ap.add_argument('--cp',type=int,help='forward cp parameter')
    ap.add_argument('--arg',action='append',default=[],metavar='KEY=VALUE',help='forward arbitrary player argument')
    a=ap.parse_args(argv)
    try:
        # Bind process configuration to the caller BEFORE opening any socket or
        # emitting UCI readiness. Never substitute localhost or a default engine.
        actual_hash=brain_fingerprint(a.brains,a.id)
        if a.expect_brain_sha256 and actual_hash != a.expect_brain_sha256:
            raise ValueError(f"brain {a.id}: brains.json no coincide con el leído por el cliente; "
                             f"archivo={Path(a.brains).resolve()} SHA256={actual_hash} "
                             f"esperado={a.expect_brain_sha256}")
        nurse=Nurse(a.brains,a.id)
        if a.expect_endpoint:
            if nurse.cfg['_type'] != 'external':
                raise ValueError('--expect-endpoint solo admite brains de tipo external')
            from .config import parse_external_endpoint
            required=parse_external_endpoint({'url':a.expect_endpoint})
            configured=(nurse.cfg['ipaddress'],nurse.cfg['port'])
            if (required[0].casefold(),required[1]) != (configured[0].casefold(),configured[1]):
                raise ValueError(f"brain {a.id}: endpoint distinto entre cliente y Nurse: "
                                 f"esperado={a.expect_endpoint}, efectivo={configured[0]}:{configured[1]}; "
                                 f"brains={Path(a.brains).resolve()}")
            log(f'🔒 external configuración verificada brain={a.id} '
                f'brains={Path(a.brains).resolve()} endpoint={configured[0]}:{configured[1]} '
                f'sha256={actual_hash[:16]}')
        if nurse.cfg['_type']=='nurse':
            for attr,key in [('depth','Depth'),('qdepth','QDepth'),('timeout','timeout')]:
                value=getattr(a,attr)
                if value is not None:nurse.cfg[key]=value
            user=dict(nurse.cfg.get('arguments',{}))
            if a.cp is not None:user['cp']=a.cp
            for token in a.arg:
                if '=' not in token:raise ValueError('--arg exige KEY=VALUE')
                k,v=token.split('=',1);user[k]=v
            nurse.cfg['arguments']=user
        if a.timeout is not None:
            if a.timeout < 1:raise ValueError('--timeout debe ser >0')
            nurse.timeout=a.timeout/1000;nurse.cfg['timeout']=a.timeout
        if a.tmax is not None:
            if a.tmax < 1:raise ValueError('--tmax debe ser >0')
            nurse.tmax=a.tmax;nurse.cfg['tmax']=a.tmax
            nurse.cfg['warmup_movetime']=a.tmax
        log(f'⚙️ timing efectivo tmax={nurse.tmax}ms timeout={nurse.cfg["timeout"]}ms warmup_movetime={nurse.cfg["warmup_movetime"]}ms')
        # A remote engine must be reachable and UCI-ready BEFORE Nurse tells
        # the benchmark that the frontend is ready. Never succeed with a
        # synthetic uciok when no remote engine has connected.
        if nurse.cfg['_type']=='external':
            nurse._ensure()
        return nurse.run()
    except KeyboardInterrupt:
        log('🛑 Interrupción del usuario (Ctrl+C): Nurse finalizando voluntariamente')
        return 130
    except Exception as exc:
        log(f'❌ fatal: {exc}')
        return 2
if __name__=='__main__':raise SystemExit(main())
