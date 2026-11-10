# Sargon-NNUE generic UCI process adapter v0.6.209
"""UCI stdio subprocess adapter. No shell, no network, no internal position evaluator.

A child UCI engine owns its search and evaluation. Child stdout is parsed strictly
as UCI; child stderr is copied exclusively to parent stderr. Each search is
serialized and completed only after bestmove (or a bounded failure).
"""
from __future__ import annotations
import os
import shutil
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import chess

from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP

_STAT = re.compile(r'(?<!\S)(depth|nodes|time)\s+(\d+)(?=\s|$)')
_SCORE = re.compile(r'(?<!\S)score\s+(cp|mate)\s+(-?\d+)(?=\s|$)')
_GO_LIMIT = re.compile(r'(?<!\S)(movetime|depth|nodes|wtime|btime|infinite|mate)\b')


class GenericUCIPlayer(Player):
    name = 'UCI'

    def __init__(self, executable: str, args: list[str], *, tmax_ms: int = 15000,
                 timeout_ms: int = 30000, telemetry=None):
        if not isinstance(args, list) or any(not isinstance(a,str) for a in args):
            raise PlayerError('UCI: args debe ser lista de cadenas')
        if not executable or not isinstance(executable,str):
            raise PlayerError('UCI: engine-path debe indicar un ejecutable')
        self.tmax_ms = int(tmax_ms)
        self.timeout_ms = int(timeout_ms)
        if self.tmax_ms <= 0 or self.timeout_ms <= 0:
            raise PlayerError('UCI: tmax y timeout deben ser positivos (ms)')
        self.telemetry = telemetry
        # Also resolve direct use of GenericUCIPlayer, not just brains.get().
        requested = str(Path(executable).expanduser())
        if Path(requested).is_absolute():
            resolved = str(Path(requested).resolve()) if Path(requested).is_file() else requested
        else:
            project = Path(__file__).resolve().parents[3]
            options = (project / 'scripts', Path.cwd(), project)
            resolved = next((str((base / requested).resolve()) for base in options
                             if (base / requested).is_file()), None)
            if resolved is None:
                resolved = shutil.which(requested) or requested
        self.command = [resolved, *args]
        self.last_info: list[str] = []
        self._q: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.RLock()
        self._closed = False
        self._log(f'launch cwd={os.getcwd()} requested={executable!r} resolved={resolved!r} args={args!r}')
        if not (Path(resolved).is_file() or shutil.which(resolved)):
            raise PlayerError(f'UCI: ejecutable no encontrado: {executable!r} (resuelto={resolved!r}; cwd={os.getcwd()!r})')
        try:
            self.proc = subprocess.Popen(
                self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                bufsize=1, shell=False,
                creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                if os.name == 'nt' else 0,
            )
        except (OSError, ValueError) as exc:
            raise PlayerError(f'UCI: no se pudo ejecutar {self.command[0]}: {exc}') from exc
        try:
            threading.Thread(target=self._read_stdout, daemon=True, name='uci-stdout').start()
            threading.Thread(target=self._read_stderr, daemon=True, name='uci-stderr').start()
            self._log(f'pid={self.proc.pid} handshake start')
            self._send('uci')
            self._until('uciok', self.timeout_ms)
            self._send('isready')
            self._until('readyok', self.timeout_ms)
            self._log(f'handshake complete uciok/readyok pid={self.proc.pid}')
        except BaseException:
            self.close()
            raise

    def _log(self, message: str) -> None:
        if self.telemetry:
            self.telemetry('⚙️ UCI ' + message)
        else:
            print('⚙️ UCI ' + message, file=sys.stderr, flush=True)

    def _read_stdout(self) -> None:
        try:
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self._q.put(line.rstrip('\r\n'))
        finally:
            self._q.put(None)

    def _read_stderr(self) -> None:
        try:
            assert self.proc.stderr is not None
            for line in self.proc.stderr:
                # stderr is never sent into the UCI protocol output stream.
                self._log('child stderr: ' + line.rstrip('\r\n'))
        except (OSError, ValueError):
            pass

    def _send(self, line: str) -> None:
        if self.proc.poll() is not None:
            raise PlayerError(f'UCI: proceso terminó exit={self.proc.returncode} antes de {line!r}')
        self._log('stdin ' + line)
        try:
            assert self.proc.stdin is not None
            self.proc.stdin.write(line + '\n')
            self.proc.stdin.flush()
        except (OSError, ValueError) as exc:
            raise PlayerError(f'UCI: error escribiendo comando {line!r}: {exc}') from exc

    def _until(self, prefix: str, timeout_ms: int, *, collect: bool = False) -> str:
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'UCI: timeout esperando {prefix} ({timeout_ms} ms); pid={self.proc.pid} exit={self.proc.poll()} cmd={self.command!r}')
            try:
                line = self._q.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f'UCI: timeout esperando {prefix} ({timeout_ms} ms); pid={self.proc.pid} exit={self.proc.poll()} cmd={self.command!r}') from exc
            if line is None:
                raise PlayerError(f'UCI: EOF esperando {prefix}, exit={self.proc.poll()}')
            if line.startswith(('uciok', 'readyok', 'bestmove ', 'id name ', 'info string ')):
                self._log('stdout ' + line[:320])
            if collect and line.startswith('info '):
                self.last_info.append(line)
            if line == prefix or line.startswith(prefix + ' '):
                return line

    def is_ready(self) -> None:
        with self._lock:
            self._send('isready')
            self._until('readyok', self.timeout_ms)

    def new_game(self) -> None:
        with self._lock:
            self._send('ucinewgame')
            self.is_ready()

    def _position(self, board: chess.Board) -> str:
        if board.move_stack:
            root = board.root()
            lead = 'position startpos' if root.fen() == chess.Board().fen() else 'position fen ' + root.fen()
            return lead + ' moves ' + ' '.join(move.uci() for move in board.move_stack)
        return 'position fen ' + board.fen()

    def choose(self, board: chess.Board, *, go_command: str | None = None) -> MoveChoice:
        with self._lock:
            if self._closed: raise PlayerError('UCI: player cerrado')
            if board.is_game_over(claim_draw=True):
                return MoveChoice(None, 0, 0, 0, 0.0, 'UCI')
            self.is_ready()
            self._send(self._position(board))
            # For MATCH/BENCHMARK go is bare; tmax supplies the search budget.
            # Explicit bounded UCI go options sent by LISTEN are retained.
            go = go_command.strip() if go_command else 'go'
            if not go.startswith('go') or (len(go) > 2 and go[2] != ' '):
                raise PlayerError(f'UCI: comando go inválido: {go!r}')
            if not _GO_LIMIT.search(go) or 'infinite' in go.split():
                go = 'go movetime ' + str(self.tmax_ms)
            self.last_info = []
            t0 = time.monotonic()
            self._send(go)
            # Timeout is a maximum wait on top of the declared movetime budget.
            # For explicit clock controls use the configured timeout only.
            cap = self.timeout_ms
            if 'movetime' in go.split():
                parts = go.split()
                try: cap = max(cap, int(parts[parts.index('movetime') + 1]) + self.timeout_ms)
                except (ValueError, IndexError): pass
            try:
                line = self._until('bestmove', cap, collect=True)
            except BaseException:
                try: self._send('stop')
                except Exception: pass
                # Do not reuse a potentially desynchronized UCI process.
                self.close()
                raise
            elapsed_ms = (time.monotonic() - t0) * 1000
            parts = line.split()
            token = parts[1] if len(parts) >= 2 else '(none)'
            if token in ('(none)', '0000'):
                raise PlayerError('UCI: bestmove vacío en posición no terminal')
            try:
                move = chess.Move.from_uci(token)
            except ValueError as exc:
                raise PlayerError(f'UCI: bestmove inválido: {token}') from exc
            if move not in board.legal_moves:
                raise PlayerError(f'UCI: bestmove ilegal: {token} fen={board.fen()}')
            stats = {'depth': 0, 'nodes': 0, 'time': 0}
            score_cp = 0
            for info in self.last_info:
                for match in _STAT.finditer(info):
                    stats[match.group(1)] = int(match.group(2))
                score = _SCORE.search(info)
                if score:
                    value = int(score.group(2))
                    score_cp = value if score.group(1) == 'cp' else (MATE_CP - abs(value)) * (1 if value >= 0 else -1)
            # UCI score is conventionally from the perspective of the side to move.
            self._log(f'bestmove {token} depth={stats["depth"]} nodes={stats["nodes"]} elapsed={elapsed_ms:.1f}ms')
            return MoveChoice(move, score_cp, stats['depth'], stats['nodes'], elapsed_ms, 'UCI')

    def stop(self) -> None:
        # This is safe when called between searches; synchronous UCISession
        # does not currently process stop concurrently with choose().
        with self._lock:
            if self.proc.poll() is None:
                self._send('stop')

    def close(self) -> None:
        if self._closed: return
        self._closed = True
        with self._lock:
            if self.proc.poll() is None:
                try: self._send('quit')
                except Exception: pass
                try: self.proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    self.proc.terminate()
                    try: self.proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait(timeout=2.0)
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                if stream:
                    try: stream.close()
                    except (OSError, ValueError): pass
