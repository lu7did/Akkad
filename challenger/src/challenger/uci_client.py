from __future__ import annotations

import queue
import socket
import threading
import time
from dataclasses import dataclass


class UCIError(RuntimeError):
    pass


@dataclass(slots=True)
class BestMove:
    move: str
    ponder: str | None = None


class TCPUCIClient:
    def __init__(self, host: str, port: int, timeout_ms: int = 120000, verbose: bool = False):
        self.host = host
        self.port = int(port)
        self.timeout_ms = int(timeout_ms)
        if self.timeout_ms <= 0:
            raise ValueError("timeout_ms debe ser > 0")
        self.timeout_seconds = self.timeout_ms / 1000.0
        self.verbose = verbose
        self.sock: socket.socket | None = None
        self.file = None
        self._rx: queue.Queue[str | None] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self.options: set[str] = set()
        self.id_name = "unknown"

    @property
    def connected(self) -> bool:
        return self.sock is not None

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout_seconds)
        self.sock.settimeout(None)
        self.file = self.sock.makefile("r", encoding="utf-8", errors="replace", newline="\n")
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()
        self.send("uci")
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            line = self.recv_until(deadline)
            if line == "uciok": break
            low = line.lower()
            if low.startswith("id name "): self.id_name = line[8:].strip()
            elif low.startswith("option name "):
                body = line[12:]
                name = body.split(" type ", 1)[0].strip()
                if name: self.options.add(name)
        self.isready()

    def _reader(self) -> None:
        try:
            assert self.file is not None
            for raw in self.file:
                line = raw.strip()
                if line:
                    if self.verbose: print(f"[UCI <-] {line}")
                    self._rx.put(line)
        except Exception:
            pass
        finally:
            self._rx.put(None)

    def send(self, line: str) -> None:
        if not self.sock: raise UCIError("No conectado")
        if self.verbose: print(f"[UCI ->] {line}")
        try:
            self.sock.sendall((line.rstrip() + "\n").encode("utf-8"))
        except OSError as exc:
            raise UCIError(f"Fallo enviando UCI: {exc}") from exc

    def recv_until(self, deadline: float) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise TimeoutError("Timeout esperando respuesta UCI")
        try: line = self._rx.get(timeout=remaining)
        except queue.Empty as exc: raise TimeoutError("Timeout esperando respuesta UCI") from exc
        if line is None: raise UCIError("El motor UCI cerró la conexión")
        return line

    def isready(self) -> None:
        self.send("isready")
        deadline = time.monotonic() + self.timeout_seconds
        while self.recv_until(deadline) != "readyok":
            pass

    def new_game(self) -> None:
        self.send("ucinewgame")
        self.isready()

    def setoption(self, name: str, value: str | None = None) -> None:
        if value is None: self.send(f"setoption name {name}")
        else: self.send(f"setoption name {name} value {value}")

    def position(self, moves: list[str]) -> None:
        suffix = "" if not moves else " moves " + " ".join(moves)
        self.send("position startpos" + suffix)

    def go(self, wtime_ms: int, btime_ms: int, response_timeout: float | None = None) -> BestMove:
        self.send(f"go wtime {max(0,wtime_ms)} btime {max(0,btime_ms)}")
        wait = self.timeout_seconds if response_timeout is None else max(0.001, float(response_timeout))
        deadline = time.monotonic() + wait
        while True:
            line = self.recv_until(deadline)
            if line.startswith("bestmove "):
                parts = line.split()
                return BestMove(parts[1], parts[3] if len(parts) >= 4 and parts[2] == "ponder" else None)

    def stop(self) -> None:
        if self.connected:
            try: self.send("stop")
            except UCIError: pass

    def report_result_if_supported(self, token: str, reason: str) -> None:
        candidates = [name for name in self.options if name.lower().endswith("result")]
        if not candidates: return
        preferred = "NyxResult" if "NyxResult" in candidates else sorted(candidates)[0]
        try:
            self.setoption(preferred, f"{token} reason {reason}")
            self.isready()
        except Exception:
            pass

    def close(self) -> None:
        if self.sock:
            try: self.send("quit")
            except Exception: pass
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: self.sock.close()
            except OSError: pass
            self.sock = None
