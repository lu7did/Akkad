# Sargon-NNUE v0.6.166 - UCI over TCP, remote engine owns its configuration.
from __future__ import annotations
import queue
import socket
import threading
import time
import re
import chess
from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP

_ENDPOINT = re.compile(r"^(?P<host>\[[0-9a-fA-F:]+\]|[A-Za-z0-9][A-Za-z0-9._-]*):(?P<port>[0-9]{1,5})$")

def parse_endpoint(url: str) -> tuple[str, int]:
    if not isinstance(url, str):
        raise ValueError('external: url debe ser host:puerto')
    m = _ENDPOINT.fullmatch(url.strip())
    if not m:
        raise ValueError('external: url inválida; usar host:puerto sin protocolo')
    host = m.group('host').strip('[]')
    port = int(m.group('port'))
    if not 1 <= port <= 65535:
        raise ValueError('external: puerto fuera de rango 1..65535')
    return host, port

class TCPExternalUCIPlayer(Player):
    """Transparent remote UCI player: no engine tuning, evaluation, or local search."""
    name = 'EXTERNAL'
    def __init__(self, url: str, *, timeout_ms: int = 30000):
        try: self.host, self.port = parse_endpoint(url)
        except ValueError as exc: raise PlayerError(str(exc)) from exc
        self.timeout_ms = int(timeout_ms)
        if self.timeout_ms <= 0: raise PlayerError('external: timeout debe ser positivo')
        self.q = queue.Queue()
        self.sock = None
        self._closed = False
        try:
            self.sock = socket.create_connection((self.host,self.port), timeout=min(self.timeout_ms/1000, 30))
            self.sock.settimeout(None)
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            self._send('uci')
            self._await('uciok')
            self._send('isready')
            self._await('readyok')
            self._send('ucinewgame')
            self._send('isready')
            self._await('readyok')
        except Exception as exc:
            self.close()
            raise PlayerError(f'external {url}: falló conexión UCI: {exc}') from exc

    def _read(self):
        try:
            with self.sock.makefile('r', encoding='utf-8', errors='replace', newline='\n') as stream:
                for line in stream: self.q.put(line.strip())
        except (OSError, ValueError): pass
        finally: self.q.put(None)

    def _send(self, command):
        if self._closed or self.sock is None: raise PlayerError('external: conexión cerrada')
        try: self.sock.sendall((command+'\n').encode('utf-8'))
        except OSError as exc: raise PlayerError(f'external: error enviando {command}: {exc}') from exc

    def _await(self, prefix):
        end=time.monotonic()+self.timeout_ms/1000
        while True:
            remaining=end-time.monotonic()
            if remaining<=0: raise PlayerError(f'external: timeout esperando {prefix}')
            try: line=self.q.get(timeout=remaining)
            except queue.Empty: raise PlayerError(f'external: timeout esperando {prefix}')
            if line is None: raise PlayerError('external: el servidor cerró la sesión')
            if line.startswith(prefix): return line

    def choose(self, board: chess.Board) -> MoveChoice:
        start=time.monotonic()
        self._send('position fen '+board.fen())
        # The remote server owns search limits. Bare UCI go passes no tuning.
        self._send('go')
        line=self._await('bestmove ')
        parts=line.split()
        if len(parts)<2: raise PlayerError('external: bestmove sin jugada')
        token=parts[1]
        if token in ('(none)','0000'):
            if not board.is_game_over(claim_draw=True):
                raise PlayerError('external: bestmove vacío en posición no terminal')
            move=None
        else:
            try: move=chess.Move.from_uci(token)
            except ValueError as exc: raise PlayerError(f'external: bestmove inválido: {token}') from exc
            if move not in board.legal_moves: raise PlayerError(f'external: bestmove ilegal: {token}')
        return MoveChoice(move, 0, 0, 0, (time.monotonic()-start)*1000, self.name)

    def close(self):
        if self._closed: return
        if self.sock is not None:
            try: self._send('quit')
            except Exception: pass
            self._closed=True
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.sock.close()
        else: self._closed=True
