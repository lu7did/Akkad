"""Process/TCP transports. All wire protocol is plain UTF-8, line buffered, no BOM."""
import os,sys,socket,subprocess,threading,queue,time,json
from .telemetry import log

class TransportError(RuntimeError):pass

class Transport:
    def __init__(self):
        self.q=queue.Queue();self.closed=False;self._write_lock=threading.RLock()
        self.proc=None;self.sock=None;self.wire_uci=False;self.uci_name=None;self.peer_address=None
        self.local_address=None;self.resolved_addresses=();self.requested_endpoint=None
    def _read_process(self):
        try:
            for line in self.proc.stdout:
                line=line.rstrip('\r\n')
                if self.wire_uci:log(f'⬅️ UCI stdout {line}')
                self.q.put(line)
        finally:self.q.put(None)
    def _read_stderr(self):
        try:
            for line in self.proc.stderr:log('📋 child '+line.rstrip('\r\n'))
        except (OSError,ValueError):pass
    def process(self,command,cwd=None):
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0
        try:
            self.proc=subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',bufsize=1,creationflags=flags)
        except (OSError,ValueError) as e:raise TransportError(f"no se pudo lanzar {command}: {e}") from e
        log(f"🚀 subprocess pid={self.proc.pid} cwd={cwd or os.getcwd()} argv={command!r}")
        threading.Thread(target=self._read_process,daemon=True).start()
        threading.Thread(target=self._read_stderr,daemon=True).start()
        return self
    def _read_tcp(self):
        buffer=b''
        try:
            while not self.closed:
                chunk=self.sock.recv(4096)
                if not chunk:break
                buffer+=chunk
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1)
                    message=line.decode('utf-8','replace').rstrip('\r')
                    if self.wire_uci:log(f'⬅️ UCI tcp {message}')
                    self.q.put(message)
        except OSError as exc:
            if not self.closed:log(f'⚠️ TCP lectura interrumpida: {exc}')
        finally:
            self.q.put(None)
            if not self.closed:log('🔌 TCP desconectado')
    def tcp(self,host,port,timeout=10):
        """Log both DNS resolution and the REAL connected socket addresses.

        Never infer the connection destination from DNS alone: IPv4/IPv6,
        resolver ordering and multi-address hosts may select another address.
        """
        port=int(port)
        self.requested_endpoint=(host,port)
        try:
            addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
        except OSError as exc:
            raise TransportError(f'DNS falló para {host}:{port}: {exc}') from exc
        ips=tuple(dict.fromkeys(item[4][0] for item in addresses))
        self.resolved_addresses=ips
        log(f'🌐 TCP DNS host={host!r} port={port} resolved={list(ips)!r}')
        if not addresses:
            raise TransportError(f'DNS sin direcciones TCP para {host}:{port}')
        try:
            # Try the resolver results in order while capturing the precise
            # address that accepted the connection (no localhost fallback).
            last_error=None
            for family,kind,proto,canon,sockaddr in addresses:
                candidate=None
                try:
                    candidate=socket.socket(family,kind,proto)
                    candidate.settimeout(timeout)
                    candidate.connect(sockaddr)
                    self.sock=candidate
                    break
                except OSError as exc:
                    last_error=exc
                    if candidate is not None:candidate.close()
            if self.sock is None:
                raise TransportError(f'no se pudo conectar a {host}:{port}; DNS={list(ips)!r}; último error={last_error}')
            self.sock.settimeout(None)
            self.peer_address=self.sock.getpeername()
            self.local_address=self.sock.getsockname()
        except OSError as exc:
            raise TransportError(f'no se pudo conectar a {host}:{port} DNS={list(ips)!r}: {exc}') from exc
        log(f'✅ TCP socket fd={self.sock.fileno()} requested={host}:{port} '
            f'resolved={list(ips)!r} peer={self.peer_address!r} '
            f'local={self.local_address!r}')
        threading.Thread(target=self._read_tcp,daemon=True).start()
        return self
    def provenance(self):
        """Diagnostic source of truth: the actual connected socket, not a label."""
        if self.sock is None or self.closed:
            raise TransportError('sin socket TCP activo')
        peer=self.sock.getpeername()
        local=self.sock.getsockname()
        host,port=self.requested_endpoint
        return {'requested':f'{host}:{port}',
                'dns':list(self.resolved_addresses),
                'peer_ip':peer[0], 'peer_port':peer[1],
                'local_ip':local[0], 'local_port':local[1],
                'uci_name':self.uci_name}
    def send(self,line):
        with self._write_lock:
            try:
                if self.wire_uci:log(f'➡️ UCI stdin {line}')
                if self.proc:
                    if self.proc.poll() is not None:raise TransportError(f'proceso terminó: {self.proc.returncode}')
                    self.proc.stdin.write(line+'\n');self.proc.stdin.flush()
                elif self.sock:self.sock.sendall((line+'\n').encode('utf-8'))
                else:raise TransportError('transporte no iniciado')
            except (BrokenPipeError,OSError,ValueError) as e:raise TransportError(str(e)) from e
    def recv(self,timeout):
        try:line=self.q.get(timeout=timeout)
        except queue.Empty:raise TimeoutError('timeout esperando respuesta')
        if line is None:raise TransportError('EOF inesperado')
        return line
    def handshake(self,timeout,options=()):
        self.send('uci')
        self.until('uciok',timeout)
        for name,value in options:
            line='setoption name '+name
            if value is not None:line+=' value '+value
            self.send(line)
        self.send('isready')
        self.until('readyok',timeout)
        log('✅ handshake UCI completo')
    def until(self,expected,timeout):
        deadline=time.monotonic()+timeout
        while True:
            line=self.recv(max(.01,deadline-time.monotonic()))
            if line.startswith('id name '):
                self.uci_name=line[len('id name '):].strip()
            if line.startswith('id ') or line.startswith('option '):continue
            if line==expected:return
            if not self.wire_uci:log(f'⬅️ UCI init {line[:240]}')
    def close(self):
        self.closed=True
        if self.proc:
            try:
                if self.proc.poll() is None:
                    self.send('quit')
                    try:self.proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=2)
            except (TransportError,OSError):pass
            for obj in (self.proc.stdin,self.proc.stdout,self.proc.stderr):
                try:obj.close()
                except (OSError,ValueError):pass
            log(f'🔌 subprocess detenido pid={self.proc.pid}')
        if self.sock:
            try:self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:self.sock.close()
            except OSError:pass
            log('🔌 TCP cerrado')
