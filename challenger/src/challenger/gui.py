from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import chess

from .game import ChallengerRunner, GameResult, GameState

UNICODE = {
    (chess.WHITE, chess.PAWN): "♙", (chess.WHITE, chess.KNIGHT): "♘", (chess.WHITE, chess.BISHOP): "♗",
    (chess.WHITE, chess.ROOK): "♖", (chess.WHITE, chess.QUEEN): "♕", (chess.WHITE, chess.KING): "♔",
    (chess.BLACK, chess.PAWN): "♟", (chess.BLACK, chess.KNIGHT): "♞", (chess.BLACK, chess.BISHOP): "♝",
    (chess.BLACK, chess.ROOK): "♜", (chess.BLACK, chess.QUEEN): "♛", (chess.BLACK, chess.KING): "♚",
}


def _clock(seconds: float) -> str:
    s = max(0, int(seconds)); return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


class ChallengerGUI:
    def __init__(self, args):
        self.args = args
        self.root = tk.Tk()
        self.root.title(f"Challenger - {args.brain.capitalize()} UCI")
        self.cell = 72
        self.canvas = tk.Canvas(self.root, width=8*self.cell, height=8*self.cell, highlightthickness=0)
        self.canvas.pack(padx=8, pady=8)
        self.canvas.bind("<Button-1>", self.on_board_click)
        self.info = tk.Label(self.root, justify="left", anchor="w", font=("Consolas", 10))
        self.info.pack(fill="x", padx=8, pady=(0, 8))
        self.q: queue.Queue[tuple[str, object]] = queue.Queue()
        self.state: GameState | None = None
        self.started_wall = time.monotonic()
        self.closing = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.runner = ChallengerRunner(args, self.on_state, self.on_result)

    def on_state(self, state: GameState) -> None:
        self.q.put(("state", state))

    def on_result(self, result: GameResult) -> None:
        self.q.put(("result", result))

    def worker(self) -> None:
        try:
            self.runner.run()
            self.q.put(("done", None))
        except Exception as exc:
            self.q.put(("error", exc))

    def run(self) -> None:
        threading.Thread(target=self.worker, daemon=True).start()
        self.root.after(100, self.poll)
        self.root.mainloop()

    def close(self) -> None:
        self.closing = True
        try: self.runner.brain.close()
        except Exception: pass
        try: self.runner.client.close()
        except Exception: pass
        try: self.root.destroy()
        except tk.TclError: pass

    def poll(self) -> None:
        if self.closing: return
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "state":
                    self.state = payload  # type: ignore[assignment]
                    self.draw()
                elif kind == "result":
                    result = payload
                    color = "blancas" if result.challenger_color == "white" else "negras"
                    messagebox.showinfo("Challenger", f"Resultado: {result.token}\nMotivo: {result.reason}\nChallenger: {color}")
                elif kind == "error":
                    messagebox.showerror("Challenger", str(payload))
                    self.close(); return
                elif kind == "done":
                    self.close(); return
        except queue.Empty:
            pass
        self.draw()
        self.root.after(200, self.poll)

    def _view_to_square(self, x: int, y: int) -> chess.Square | None:
        if not (0 <= x < 8 * self.cell and 0 <= y < 8 * self.cell):
            return None
        vf, vr = x // self.cell, y // self.cell
        bottom = self.state.challenger_color if self.state else chess.WHITE
        file = vf if bottom == chess.WHITE else 7 - vf
        rank = 7 - vr if bottom == chess.WHITE else vr
        return chess.square(file, rank)

    def on_board_click(self, event) -> None:
        if self.args.brain != "human":
            return
        square = self._view_to_square(event.x, event.y)
        if square is None:
            return
        click = getattr(self.runner.brain, "click_square", None)
        if click is not None:
            click(square)
            self.draw()

    def draw(self) -> None:
        state = self.state
        board = state.board if state else chess.Board()
        bottom = state.challenger_color if state else chess.WHITE
        self.canvas.delete("all")
        selected = None
        if self.args.brain == "human":
            get_selected = getattr(self.runner.brain, "selected_square", None)
            if get_selected is not None:
                selected = get_selected()
        for vr in range(8):
            for vf in range(8):
                file = vf if bottom == chess.WHITE else 7-vf
                rank = 7-vr if bottom == chess.WHITE else vr
                x0, y0 = vf*self.cell, vr*self.cell
                fill = "#f0d9b5" if (file+rank)%2 else "#b58863"
                sq = chess.square(file, rank)
                if sq == selected:
                    fill = "#f6e05e"
                self.canvas.create_rectangle(x0,y0,x0+self.cell,y0+self.cell,fill=fill,outline=fill)
                piece = board.piece_at(sq)
                if piece:
                    self.canvas.create_text(x0+self.cell/2,y0+self.cell/2,text=UNICODE[(piece.color,piece.piece_type)],font=("Segoe UI Symbol",42))
        depth_info = (
            f"Depth/QDepth: {self.args.plies}/{self.args.qdepth}"
            if self.args.brain == "sargon"
            else "Depth/QDepth: n/a"
        )
        if not state:
            self.info.config(text=f"Brain: {self.args.brain} | {depth_info} | IP: {self.args.ip} | Puerto: {self.args.port} | Estado: conectando...")
            return
        now = time.monotonic()
        elapsed = now - state.started_at
        challenger_clock = state.challenger_clock
        opponent_clock = state.opponent_clock
        if state.active_color is not None and state.turn_started_at is not None:
            running = max(0.0, now - state.turn_started_at)
            if state.active_color == state.challenger_color:
                challenger_clock = max(0.0, challenger_clock - running)
            else:
                opponent_clock = max(0.0, opponent_clock - running)
        text = (
            f"Brain: {self.args.brain}   {depth_info}   IP: {self.args.ip}   Puerto: {self.args.port}   Estado: {'conectado' if state.connected else 'desconectado'}\n"
            f"Challenger: {'blancas' if state.challenger_color else 'negras'}   Última propia: {state.last_challenger}   Última rival: {state.last_opponent}\n"
            f"Reloj propio: {_clock(challenger_clock)}   Reloj rival: {_clock(opponent_clock)}   Transcurrido: {_clock(elapsed)}"
        )
        if self.args.brain == "human":
            get_status = getattr(self.runner.brain, "status_message", None)
            if get_status is not None:
                text += f"\nHumano: {get_status()}"
        self.info.config(text=text)
