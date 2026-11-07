"""Read-only UCI-stream observer for the Challenger chessboard."""
from __future__ import annotations

import queue
import socket
import threading
import tkinter as tk

import chess

from .gui import UNICODE


def parse_endpoint(text: str) -> tuple[str, int]:
    try:
        host, port_text = text.rsplit(":", 1)
        port = int(port_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError("usar HOST:PUERTO") from exc
    if not host or not 1 <= port <= 65535:
        raise ValueError("HOST:PUERTO invalido")
    return host, port


class PositionTracker:
    """Authoritative board from 'position' frames; 'bestmove' is not confirmed."""
    def __init__(self):
        self.board = chess.Board()
        self.local_color = None
        self.last_local = "-"
        self.last_remote = "-"
        self.prediction = "-"
        self.message = "Esperando partida"
        self.game_started = False

    def reset(self):
        self.__init__()

    def feed(self, line: str):
        line = line.strip()
        if line == "ucinewgame":
            self.reset()
            self.message = "Nueva partida"
            return True
        if line.startswith("position "):
            tokens = line.split()
            try:
                if len(tokens) >= 2 and tokens[1] == "startpos":
                    board = chess.Board()
                    rest = tokens[2:]
                elif len(tokens) >= 8 and tokens[1] == "fen":
                    board = chess.Board(" ".join(tokens[2:8]))
                    rest = tokens[8:]
                else:
                    return False
                if rest:
                    if rest[0] != "moves":
                        return False
                    for uci in rest[1:]:
                        board.push_uci(uci)
            except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
                self.message = "Posicion UCI invalida; ignorada"
                return True
            # Replay complete history to obtain last moves for both sides,
            # even if observer connected halfway through a game.
            previous = board.copy(stack=True)
            root = previous.root()
            last_by_color = {chess.WHITE: "-", chess.BLACK: "-"}
            for move in previous.move_stack:
                color = root.turn
                san = root.san(move)
                last_by_color[color] = san
                root.push(move)
            if self.local_color is not None:
                self.last_local = last_by_color[self.local_color]
                self.last_remote = last_by_color[not self.local_color]
            self.board = board
            self.game_started = bool(board.move_stack)
            self.message = "Partida finalizada" if board.is_game_over(claim_draw=True) else "Posicion actualizada"
            return True
        if line.startswith("go ") or line == "go":
            self.local_color = self.board.turn
            # Now the perspective is known, recalculate last moves.
            last = {chess.WHITE: "-", chess.BLACK: "-"}
            root = self.board.root()
            for move in self.board.move_stack:
                color = root.turn
                last[color] = root.san(move)
                root.push(move)
            self.last_local = last[self.local_color]
            self.last_remote = last[not self.local_color]
            self.message = "Motor local calculando"
            return True
        if line.startswith("info string monitor gameover"):
            self.message = "Partida finalizada: " + line.split()[-1]
            return True
        if line.startswith("bestmove "):
            self.prediction = line.split()[1]
            self.message = "Esperando confirmacion de FICS"
            return True
        return False


class MonitorGUI:
    def __init__(self, host: str, port: int):
        self.host, self.port = host, port
        self.root = tk.Tk()
        self.root.title(f"Challenger Monitor UCI - {host}:{port}")
        self.cell = 72
        self.canvas = tk.Canvas(self.root, width=8*self.cell, height=8*self.cell,
                                highlightthickness=0)
        self.canvas.pack(padx=8, pady=8)
        self.info = tk.Label(self.root, justify="left", anchor="w", font=("Consolas", 10))
        self.info.pack(fill="x", padx=8, pady=8)
        self.reset_button = tk.Button(self.root, text="RESET", command=self.reset_board)
        self.reset_button.pack(pady=(0, 8))
        self.tracker = PositionTracker()
        self.status = "Desconectado"
        self.events = queue.Queue(maxsize=4096)
        self.stop = threading.Event()
        self.sock = None
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.draw()

    def reset_board(self):
        self.tracker.reset()
        self.tracker.message = "RESET manual; esperando siguiente posicion UCI"
        self.draw()

    def emit(self, kind, payload):
        try:
            self.events.put_nowait((kind, payload))
        except queue.Full:
            # A gap in the UCI stream makes old state unreliable.
            try:
                self.events.get_nowait()
                self.events.put_nowait(("error", "Datos perdidos; esperando una nueva posicion"))
            except queue.Empty:
                pass

    def listen(self):
        while not self.stop.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=5) as sock:
                    self.sock = sock
                    sock.settimeout(1.0)
                    self.emit("status", "Conectado")
                    buffer = b""
                    while not self.stop.is_set():
                        try:
                            data = sock.recv(8192)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        buffer += data
                        if len(buffer) > 1024 * 1024:
                            buffer = b""
                            self.emit("error", "Frame excesivo: descartado")
                        while b"\n" in buffer:
                            frame, buffer = buffer.split(b"\n", 1)
                            self.emit("frame", frame.decode("utf-8", "replace").rstrip("\r"))
            except (OSError, ValueError) as exc:
                self.emit("status", f"Desconectado: {exc}")
            finally:
                self.sock = None
                self.emit("status", "Desconectado; reintentando")
            self.stop.wait(2.0)

    def poll(self):
        if self.stop.is_set():
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "frame":
                    self.tracker.feed(payload)
                elif kind == "status":
                    self.status = payload
                else:
                    self.tracker.message = payload
        except queue.Empty:
            pass
        self.draw()
        self.root.after(150, self.poll)

    def draw(self):
        board = self.tracker.board
        self.canvas.delete("all")
        for row in range(8):
            for col in range(8):
                file, rank = col, 7-row
                sq = chess.square(file, rank)
                x, y = col*self.cell, row*self.cell
                fill = "#f0d9b5" if (file+rank)%2 else "#b58863"
                self.canvas.create_rectangle(x, y, x+self.cell, y+self.cell, fill=fill, outline=fill)
                piece = board.piece_at(sq)
                if piece:
                    self.canvas.create_text(x+self.cell/2, y+self.cell/2,
                                            text=UNICODE[(piece.color, piece.piece_type)],
                                            font=("Segoe UI Symbol", 42))
        t = self.tracker
        turn = "blancas" if board.turn == chess.WHITE else "negras"
        perspective = ("blancas" if t.local_color == chess.WHITE else
                       "negras" if t.local_color == chess.BLACK else "por determinar")
        self.info.config(text=(
            f"Monitor {self.host}:{self.port} | {self.status}\n"
            f"Perspectiva local: {perspective} | Turno: {turn}\n"
            f"Ultima local: {t.last_local} | Ultima remota: {t.last_remote}\n"
            f"Bestmove sugerido: {t.prediction} | {t.message}"))

    def close(self):
        self.stop.set()
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.root.destroy()

    def run(self):
        threading.Thread(target=self.listen, daemon=True, name="challenger-monitor").start()
        self.root.after(150, self.poll)
        self.root.mainloop()
