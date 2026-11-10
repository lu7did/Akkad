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
#* uci_external.py
#* Implementa el jugador uci external
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import queue
import re
import subprocess
import threading
import time

import chess

from .base import Player, PlayerError
from ..types import MoveChoice, MATE_CP

_INFO_DEPTH_RE = re.compile(r"\bdepth\s+(\d+)\b", re.IGNORECASE)
_INFO_NODES_RE = re.compile(r"\bnodes\s+(\d+)\b", re.IGNORECASE)
_INFO_SCORE_RE = re.compile(r"\bscore\s+(cp|mate)\s+(-?\d+)\b", re.IGNORECASE)

_ELO_OPTION_RE = re.compile(
    r"^option name UCI_Elo type spin default -?\d+ min (-?\d+) max (-?\d+)\s*$",
    re.IGNORECASE,
)


class ExternalUCIPlayer(Player):
    """Generic UCI player controlled by movetime.

    This remains the wrapper for SUNFISH and EXTERNAL engines.  STOCKFISH uses
    the dedicated StockfishUCIPlayer below because its search limits and
    strength controls have a different contract.
    """

    name = "UCI-EXTERNAL"

    def __init__(self, command: str, movetime_ms: int = 1000,
                 timeout_ms: int = 30000, label: str = "EXTERNAL"):
        self.command = command
        self.movetime_ms = int(movetime_ms)
        self.timeout_ms = int(timeout_ms)
        self.name = label
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            shell=False,
        )
        if not self.proc.stdin or not self.proc.stdout:
            raise PlayerError("no se pudo abrir UCI externo")
        self.q: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()
        self._send("uci")
        self._wait("uciok")
        self._send("isready")
        self._wait("readyok")

    def _reader(self):
        assert self.proc.stdout
        for line in self.proc.stdout:
            self.q.put(line.strip())
        self.q.put(None)

    def _send(self, s: str):
        if self.proc.poll() is not None:
            raise PlayerError(f"{self.name} terminó inesperadamente")
        assert self.proc.stdin
        self.proc.stdin.write(s + "\n")
        self.proc.stdin.flush()

    def _wait(self, token: str) -> str:
        deadline = time.monotonic() + self.timeout_ms / 1000
        while time.monotonic() < deadline:
            try:
                line = self.q.get(timeout=max(0.001, deadline-time.monotonic()))
            except queue.Empty:
                break
            if line is None:
                break
            if line.startswith(token):
                return line
        raise TimeoutError(f"timeout esperando {token} de {self.name}")

    def choose(self, board: chess.Board) -> MoveChoice:
        t0 = time.monotonic()
        self._send("position fen " + board.fen())
        self._send(f"go movetime {self.movetime_ms}")
        line = self._wait("bestmove ")
        parts = line.split()
        move = None if len(parts) < 2 or parts[1] == "(none)" else chess.Move.from_uci(parts[1])
        if move is not None and move not in board.legal_moves:
            raise PlayerError(f"{self.name} devolvió jugada ilegal: {move}")
        return MoveChoice(move, 0, 0, 0, (time.monotonic()-t0)*1000, self.name)

    def close(self):
        if self.proc.poll() is None:
            try:
                self._send("quit")
            except Exception:
                pass
            try:
                self.proc.wait(timeout=1)
            except Exception:
                self.proc.kill()


class StockfishUCIPlayer(ExternalUCIPlayer):
    """Stockfish as a monolithic UCI player.

    Stockfish owns search *and* evaluation internally.  The surrounding engine
    therefore pairs this player only with evaluator=NULL.

    Search is bounded by both ``depth`` and ``nodes``.  Full strength is the
    default; an explicit numeric ELO enables Stockfish's UCI_LimitStrength.
    """

    name = "STOCKFISH"

    def __init__(self, command: str, *, depth: int = 20, nodes: int = 5_000_000,
                 elo: int | str | None = "max", timeout_ms: int = 30000, audit=None,
                 threads: int = 1, hash_mb: int = 256, telemetry=None):
        if depth < 1:
            raise PlayerError("Stockfish depth debe ser >= 1")
        if nodes < 0:
            raise PlayerError("Stockfish nodes debe ser >= 0 (0 desactiva el límite)")
        if threads < 1:
            raise PlayerError("Stockfish threads debe ser >= 1")
        if hash_mb < 1:
            raise PlayerError("Stockfish hash debe ser >= 1 MB")

        self.depth = int(depth)
        self.nodes = int(nodes)
        self.elo = "max" if elo is None else elo
        self.threads = int(threads)
        self.hash_mb = int(hash_mb)
        self._uci_lines: list[str] = []
        self.audit = audit
        self.telemetry = telemetry

        # Inline the startup so we can retain the UCI option advertisement.
        self.command = command
        self.movetime_ms = 0  # not used by StockfishUCIPlayer
        self.timeout_ms = int(timeout_ms)
        self.name = "STOCKFISH"
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            shell=False,
        )
        if not self.proc.stdin or not self.proc.stdout:
            raise PlayerError("no se pudo abrir Stockfish UCI")
        self.q: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

        self._send("uci")
        self._uci_lines = self._wait_collect("uciok")
        if self.audit is not None:
            self.audit.event("stockfish_player_startup", command=self.command, uci_lines=self._uci_lines)
        self._configure_strength(self.elo)
        self._send(f"setoption name Threads value {self.threads}")
        self._send(f"setoption name Hash value {self.hash_mb}")
        self._send("setoption name MultiPV value 1")
        if self.audit is not None:
            self.audit.event(
                "stockfish_player_options", threads=self.threads, hash_mb=self.hash_mb, multipv=1
            )
        self._send("isready")
        self._wait("readyok")

    def _wait_collect(self, token: str) -> list[str]:
        deadline = time.monotonic() + self.timeout_ms / 1000
        lines: list[str] = []
        while time.monotonic() < deadline:
            try:
                line = self.q.get(timeout=max(0.001, deadline-time.monotonic()))
            except queue.Empty:
                break
            if line is None:
                break
            lines.append(line)
            if line.startswith(token):
                return lines
        raise TimeoutError(f"timeout esperando {token} de {self.name}")

    def _configure_strength(self, elo: int | str | None) -> None:
        if elo is None or (isinstance(elo, str) and elo.lower() == "max"):
            self._send("setoption name UCI_LimitStrength value false")
            if self.audit is not None:
                self.audit.event("stockfish_player_strength", limit_strength=False, elo="max")
            return

        try:
            requested = int(elo)
        except (TypeError, ValueError) as exc:
            raise PlayerError("Stockfish ELO debe ser un entero o 'max'") from exc

        elo_range: tuple[int, int] | None = None
        has_limit_strength = False
        for line in self._uci_lines:
            if line.lower().startswith("option name uci_limitstrength "):
                has_limit_strength = True
            match = _ELO_OPTION_RE.match(line)
            if match:
                elo_range = (int(match.group(1)), int(match.group(2)))

        if not has_limit_strength or elo_range is None:
            raise PlayerError("Stockfish no expone UCI_LimitStrength/UCI_Elo")
        lo, hi = elo_range
        if not lo <= requested <= hi:
            raise PlayerError(f"Stockfish ELO fuera de rango: {requested}; permitido {lo}..{hi}")

        self._send("setoption name UCI_LimitStrength value true")
        self._send(f"setoption name UCI_Elo value {requested}")
        if self.audit is not None:
            self.audit.event("stockfish_player_strength", limit_strength=True, elo=requested, elo_min=lo, elo_max=hi)

    def choose(self, board: chess.Board) -> MoveChoice:
        t0 = time.monotonic()
        side_to_move = board.turn
        fen = board.fen()
        go_cmd = f"go depth {self.depth}"
        if self.nodes > 0:
            go_cmd += f" nodes {self.nodes}"
        if self.audit is not None:
            self.audit.event(
                "stockfish_player_choose_begin",
                fen=fen, turn="white" if side_to_move == chess.WHITE else "black",
                legal_moves=len(list(board.legal_moves)), depth_limit=self.depth, nodes_limit=self.nodes,
                position_cmd="position fen " + fen, go_cmd=go_cmd,
            )
        self._send("position fen " + fen)
        self._send(go_cmd)
        try:
            lines = self._wait_collect("bestmove ")
        except TimeoutError:
            if self.telemetry is not None:
                self.telemetry(
                    f"❌ GUARDRAIL STOCKFISH time: levels=0/{self.depth} "
                    f"nodes_limit={self.nodes or 'off'} nodes_pct=n/a timeout_ms={self.timeout_ms} "
                    f"fallback=no-complete-bestmove"
                )
            raise
        line = lines[-1]
        parts = line.split()
        move = None if len(parts) < 2 or parts[1] == "(none)" else chess.Move.from_uci(parts[1])
        if move is not None and move not in board.legal_moves:
            raise PlayerError(f"{self.name} devolvió jugada ilegal: {move}")

        actual_depth = 0
        actual_nodes = 0
        score_white = 0
        for info in lines:
            if not info.startswith("info "):
                continue
            m = _INFO_DEPTH_RE.search(info)
            if m:
                actual_depth = int(m.group(1))
            m = _INFO_NODES_RE.search(info)
            if m:
                actual_nodes = int(m.group(1))
            m = _INFO_SCORE_RE.search(info)
            if m:
                kind, raw = m.group(1).lower(), int(m.group(2))
                stm_score = (MATE_CP if raw > 0 else -MATE_CP) if kind == "mate" else raw
                score_white = stm_score if side_to_move == chess.WHITE else -stm_score

        elapsed_ms = (time.monotonic()-t0)*1000
        if self.nodes > 0 and actual_depth < self.depth and actual_nodes >= self.nodes:
            nodes_pct = 100.0 * actual_nodes / self.nodes if self.nodes > 0 else 0.0
            if self.telemetry is not None:
                severity = "⚠️" if actual_depth > 0 else "❌"
                self.telemetry(
                    f"{severity} GUARDRAIL STOCKFISH nodes: levels={actual_depth}/{self.depth} "
                    f"nodes={actual_nodes}/{self.nodes} nodes_pct={nodes_pct:.1f}% "
                    f"elapsed_ms={elapsed_ms:.1f}"
                )
            if self.audit is not None:
                self.audit.event(
                    "stockfish_guardrail", kind="nodes", depth_target=self.depth,
                    depth_reached=actual_depth, nodes=actual_nodes, nodes_limit=self.nodes,
                    nodes_pct=nodes_pct, elapsed_ms=elapsed_ms,
                )
        if self.audit is not None:
            self.audit.event(
                "stockfish_player_choose_end",
                fen=fen, bestmove=(move.uci() if move is not None else None),
                legal=(move is None or move in board.legal_moves),
                actual_depth=actual_depth, actual_nodes=actual_nodes, score_white_cp=score_white,
                elapsed_ms=elapsed_ms, raw_lines=lines,
            )
        return MoveChoice(
            move, score_white, actual_depth, actual_nodes,
            elapsed_ms, self.name,
        )
