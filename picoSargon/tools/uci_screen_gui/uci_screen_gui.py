#!/usr/bin/env python3
"""Monitor a GNU Screen session's visible UCI transcript and show a chessboard.

Requires: GNU Screen, Python 3.9+, python-chess. Tkinter is used for the GUI.
This is a passive monitor. It neither sends commands to the session nor assumes
that a bestmove has been played.
"""
from __future__ import annotations

import argparse
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk

try:
    import chess
except ImportError:
    raise SystemExit("Missing python-chess. Install with: python3 -m pip install python-chess")

PIECES = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}
POSITION = re.compile(r"\bposition\s+(startpos|fen\s+.+)$", re.I)
BESTMOVE = re.compile(r"\bbestmove\s+(\S+)(?:\s+ponder\s+(\S+))?", re.I)
UCI_TOKENS = re.compile(r"^(?:uci|uciok|isready|readyok|ucinewgame|quit|stop|ponderhit|go(?:\s|$)|info(?:\s|$)|id(?:\s|$)|option(?:\s|$)|setoption(?:\s|$))", re.I)
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def normalize(line: str) -> str:
    line = ANSI.sub("", line).strip()
    # Optional logging prefixes emitted by Sargon-NNUE and various bridges.
    for prefix in ("⬅️", "➡️", "⬅", "➡", "<=", "=>", "<--", "-->", "<<<", ">>>"):
        if line.startswith(prefix):
            line = line[len(prefix):].strip()
            break
    # Accept timestamps, then a visual direction marker.
    line = re.sub(r"^\[(?:\d{2}:){1,2}\d{2}(?:\.\d+)?\]\s*", "", line)
    for prefix in ("⬅️", "➡️", "⬅", "➡", "<=", "=>", "<--", "-->", "<<<", ">>>"):
        if line.startswith(prefix):
            line = line[len(prefix):].strip()
            break
    return line


class UciTracker:
    """Positions are authoritative; bestmove is a proposal, not an applied move."""
    def __init__(self):
        self.board = chess.Board()
        self.last_bestmove = "—"
        self.last_command = "—"
        self.valid = 0
        self.invalid = 0
        self.messages = 0
        self.log = []

    def add(self, level: str, message: str):
        self.log.append(f"[{level}] {message}")
        self.log = self.log[-180:]

    def feed(self, raw: str) -> bool:
        """Returns whether the display should refresh."""
        line = normalize(raw)
        if not line:
            return False
        match = POSITION.search(line)
        if match:
            expression = match.group(1)
            self.messages += 1
            self.last_command = "position"
            try:
                tokens = expression.split()
                if tokens[0] == "startpos":
                    candidate = chess.Board()
                    move_tokens = tokens[2:] if len(tokens) > 1 and tokens[1] == "moves" else []
                    if len(tokens) > 1 and tokens[1] != "moves":
                        raise ValueError("expected 'moves' after startpos")
                else:
                    if len(tokens) < 7:
                        raise ValueError("FEN must contain six fields")
                    candidate = chess.Board(" ".join(tokens[1:7]))
                    if len(tokens) > 7 and tokens[7] != "moves":
                        raise ValueError("expected 'moves' after FEN")
                    move_tokens = tokens[8:] if len(tokens) > 7 else []
                if not candidate.is_valid():
                    raise ValueError("FEN describes an invalid chess position")
                for number, token in enumerate(move_tokens, 1):
                    move = chess.Move.from_uci(token)
                    if move not in candidate.legal_moves:
                        raise ValueError(f"illegal move #{number}: {token} in {candidate.fen()}")
                    candidate.push(move)
                self.board = candidate
                self.valid += 1
                self.add("OK", f"position validated, {len(move_tokens)} moves, FEN {candidate.fen()}")
            except (ValueError, chess.InvalidMoveError, chess.InvalidFenError) as error:
                self.invalid += 1
                self.add("ERROR", f"rejected position: {error}")
            return True
        match = BESTMOVE.search(line)
        if match:
            self.messages += 1
            token = match.group(1)
            self.last_command = "bestmove"
            if token in ("(none)", "0000"):
                self.last_bestmove = token
                self.valid += 1
                self.add("INFO", f"bestmove {token} (no move)")
            else:
                try:
                    move = chess.Move.from_uci(token)
                    if move in self.board.legal_moves:
                        self.valid += 1
                        self.last_bestmove = token
                        self.add("OK", f"bestmove {token}, legal in last confirmed position; not applied")
                    else:
                        # A trace may contain searches whose 'position' input was not visible.
                        self.invalid += 1
                        self.last_bestmove = token
                        self.add("WARN", f"bestmove {token} illegal in last visible position; missing UCI input or stale state?")
                except chess.InvalidMoveError:
                    self.invalid += 1
                    self.add("ERROR", f"invalid bestmove syntax: {token}")
            return True
        if UCI_TOKENS.match(line):
            self.messages += 1
            self.last_command = line.split()[0]
            if line == "ucinewgame":
                # UCI ucinewgame clears search history, not necessarily board state.
                self.add("INFO", "ucinewgame: awaiting next position command")
            elif self.last_command == "info":
                return True
            elif self.last_command == "go":
                self.add("INFO", line[:120])
            else:
                self.add("INFO", line[:120])
            return True
        return False


def screen_cmd(session: str, *args: str):
    return subprocess.run(["screen", "-S", session, "-X", *args], text=True,
                          capture_output=True, timeout=8)


def verify_session(session: str):
    try:
        result = subprocess.run(["screen", "-ls"], text=True, capture_output=True, timeout=8)
    except FileNotFoundError as error:
        raise RuntimeError("GNU Screen is not installed or is not in PATH") from error
    output = result.stdout + result.stderr
    # Require an exact session identifier/name shown by screen -ls, avoiding substring matches.
    entries = re.findall(r"^[ \t]*(\d+\.[^\s]+)[ \t]+[^\r\n]*?\((?:Attached|Detached)\)", output, re.M)
    matched = [e for e in entries if e == session or e.split(".", 1)[1] == session]
    if len(matched) != 1:
        raise RuntimeError(f"Expected exactly one session named '{session}', found {len(matched)}.\n{output}")
    return matched[0]


class ScreenMonitor(threading.Thread):
    def __init__(self, session: str, updates: queue.Queue, stop: threading.Event,
                 interval: float, flush: int):
        super().__init__(daemon=True)
        self.session, self.updates, self.stop_event = session, updates, stop
        self.interval, self.flush = interval, flush
        self.path = ""
        self.started_logging = False

    def send(self, kind, value):
        self.updates.put((kind, value))

    def run(self):
        try:
            active = verify_session(self.session)
            self.send("state", f"Connected to Screen session {active}")
            with tempfile.TemporaryDirectory(prefix="uci-screen-") as tempdir:
                self.path = os.path.join(tempdir, "transcript.log")
                open(self.path, "wb").close()
                for args in (("logfile", self.path), ("logfile", "flush", str(self.flush)), ("log", "on")):
                    result = screen_cmd(active, *args)
                    if result.returncode:
                        raise RuntimeError(f"screen command failed ({' '.join(args)}): {result.stderr.strip()}")
                self.started_logging = True
                # New output is appended to Screen's log, potentially buffered by flush seconds.
                with open(self.path, "r", encoding="utf-8", errors="replace") as inp:
                    fragment = ""
                    while not self.stop_event.wait(self.interval):
                        chunk = inp.read()
                        if not chunk:
                            continue
                        fragment += chunk.replace("\r", "\n")
                        while "\n" in fragment:
                            line, fragment = fragment.split("\n", 1)
                            self.send("line", line)
                        if len(fragment) > 65536:
                            fragment = fragment[-8192:]
                            self.send("state", "Warning: line without newline truncated")
        except Exception as error:
            self.send("error", str(error))
        finally:
            if self.started_logging:
                try:
                    screen_cmd(self.session, "log", "off")
                except Exception:
                    pass
            self.send("state", "Monitor stopped")


class App:
    TILE = 68
    def __init__(self, root: tk.Tk, args):
        self.root = root
        self.args = args
        self.tracker = UciTracker()
        self.queue = queue.Queue()
        self.stop = threading.Event()
        self.root.title("UCI Screen Observer")
        self.status = tk.StringVar(value="Connecting…")
        self.details = tk.StringVar()
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")
        main = ttk.Frame(frame)
        main.pack(fill="both", expand=True, pady=6)
        self.canvas = tk.Canvas(main, width=self.TILE*8, height=self.TILE*8, highlightthickness=0)
        self.canvas.pack(side="left")
        right = ttk.Frame(main, padding=(12, 0))
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, textvariable=self.details, justify="left").pack(anchor="w", pady=(0, 10))
        ttk.Label(right, text="Validated UCI transcript").pack(anchor="w")
        self.logbox = tk.Text(right, width=66, height=25, wrap="word", state="disabled")
        self.logbox.pack(fill="both", expand=True)
        self.draw()
        self.thread = ScreenMonitor(args.session, self.queue, self.stop, args.poll, args.flush)
        self.thread.start()
        self.root.after(100, self.pump)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def draw(self):
        c, n, board = self.canvas, self.TILE, self.tracker.board
        c.delete("all")
        for rank_from_top in range(8):
            for file_idx in range(8):
                square = chess.square(file_idx, 7-rank_from_top)
                x, y = file_idx*n, rank_from_top*n
                light = (file_idx + rank_from_top) % 2 == 0
                c.create_rectangle(x, y, x+n, y+n, fill="#f0d9b5" if light else "#b58863", outline="")
                piece = board.piece_at(square)
                if piece:
                    ch = PIECES[piece.symbol()]
                    color = "#fafafa" if piece.color == chess.WHITE else "#171717"
                    c.create_text(x+n/2, y+n/2, text=ch, fill=color,
                                  font=("DejaVu Sans", 42))
                if file_idx == 0:
                    c.create_text(x+9, y+9, text=str(8-rank_from_top), font=("Arial", 9), fill="#333333")
                if rank_from_top == 7:
                    c.create_text(x+n-9, y+n-9, text=chr(97+file_idx), font=("Arial", 9), fill="#333333")
        t = self.tracker
        self.details.set(f"To move: {'White' if board.turn else 'Black'}\n"
                         f"Full move: {board.fullmove_number}\n"
                         f"Last bestmove: {t.last_bestmove}\n"
                         f"Last UCI command: {t.last_command}\n"
                         f"Valid: {t.valid} | Warnings/errors: {t.invalid}\n"
                         f"Observed UCI messages: {t.messages}\n\nFEN:\n{board.fen()}")

    def pump(self):
        dirty = False
        new_logs = []
        try:
            for _ in range(500):
                kind, value = self.queue.get_nowait()
                if kind == "line":
                    if self.tracker.feed(value):
                        dirty = True
                        new_logs.append(self.tracker.log[-1])
                elif kind == "state":
                    self.status.set(value)
                elif kind == "error":
                    self.status.set("ERROR: " + value)
                    self.tracker.add("ERROR", value)
                    new_logs.append(self.tracker.log[-1])
        except queue.Empty:
            pass
        if new_logs:
            self.logbox.configure(state="normal")
            for log in new_logs:
                self.logbox.insert("end", log + "\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        if dirty:
            self.draw()
        if not self.stop.is_set():
            self.root.after(100, self.pump)

    def close(self):
        self.stop.set()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Observe UCI text emitted by a GNU Screen session")
    parser.add_argument("session", help="GNU Screen session name or full PID.name")
    parser.add_argument("--poll", type=float, default=0.25, help="Log polling interval in seconds (default 0.25)")
    parser.add_argument("--flush", type=int, default=1, help="Screen logfile flush in seconds (default 1)")
    args = parser.parse_args()
    if args.poll <= 0 or args.flush < 1:
        parser.error("--poll must be > 0 and --flush must be >= 1")
    root = tk.Tk()
    App(root, args)
    root.mainloop()

if __name__ == "__main__":
    main()
