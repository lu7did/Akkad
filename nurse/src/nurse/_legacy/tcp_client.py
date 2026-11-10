#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* tcp_client.py
#* Implementa funciones del modulo tcp client
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
import socket, time

class TCPUCIClient:
    def __init__(self,host="127.0.0.1",port=6200,timeout_ms=120000):
        self.host=host; self.port=port; self.timeout=timeout_ms/1000; self.sock=None; self.file=None
    def connect(self):
        self.sock=socket.create_connection((self.host,self.port),timeout=self.timeout); self.sock.settimeout(self.timeout)
        self.file=self.sock.makefile("r",encoding="utf-8",errors="replace",newline="\n")
        self.send("uci"); self._until("uciok"); self.send("isready"); self._until("readyok")
    def send(self,s): self.sock.sendall((s+"\n").encode())
    def _until(self,prefix):
        deadline=time.monotonic()+self.timeout
        while time.monotonic()<deadline:
            line=self.file.readline()
            if not line: raise ConnectionError("UCI cerró conexión")
            line=line.strip()
            if line.startswith(prefix): return line
        raise TimeoutError(prefix)
    def bestmove(self,moves:list[str]):
        self.send("position startpos"+(" moves "+" ".join(moves) if moves else "")); self.send("go")
        line=self._until("bestmove "); return line.split()[1]
    def close(self):
        sock, file = self.sock, self.file
        self.sock, self.file = None, None
        if sock:
            try:
                sock.sendall(b"quit\n")
            except Exception:
                pass
        if file:
            try:
                file.close()
            except Exception:
                pass
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
