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
#* stockfish.py
#* Implementa el evaluador stockfish
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from collections import deque, OrderedDict
from pathlib import Path

import chess

from .base import Evaluator, EvaluatorError
from ..types import MATE_CP

_FINAL_RE = re.compile(r"Final evaluation\s*:?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", re.IGNORECASE)
_SCORE_RE = re.compile(r"\bscore\s+(cp|mate)\s+(-?\d+)\b", re.IGNORECASE)


class StockfishEvaluator(Evaluator):
    """Static evaluator backed by a persistent Stockfish process.

    Normal positions are evaluated with Stockfish's non-UCI ``eval`` command
    and the *Final evaluation* line is translated to centipawns from White's
    perspective.  This preserves the common evaluator contract used by every
    Sargon player.

    Stockfish deliberately refuses to trace a static evaluation while the side
    to move is in check.  For that exceptional case this adapter uses a one-ply
    Stockfish search as an evasion heuristic and converts its UCI score back to
    White's perspective.  Terminal positions are handled locally and never sent
    to the backend.
    """

    name = "STOCKFISH"
    trainable = False

    def __init__(
        self,
        network_path: str | None,
        engine_path: str,
        *,
        timeout_ms: int = 5000,
        check_depth: int = 1,
        cache_size: int = 100_000,
        audit=None,
    ) -> None:
        if not engine_path:
            raise EvaluatorError("--stockfish-path es obligatorio para evaluator=stockfish")
        if timeout_ms < 100:
            raise EvaluatorError("stockfish timeout debe ser >= 100 ms")
        if check_depth < 1:
            raise EvaluatorError("stockfish check depth debe ser >= 1")
        if cache_size < 0:
            raise EvaluatorError("stockfish cache size debe ser >= 0")

        self.network_path = (
            str(Path(network_path).expanduser().resolve()) if network_path else None
        )
        self.engine_path = str(Path(engine_path).expanduser().resolve())
        self.timeout_s = timeout_ms / 1000.0
        self.check_depth = int(check_depth)
        self.cache_size = int(cache_size)
        self._cache: OrderedDict[str, int] = OrderedDict()
        self.cache_hits = 0
        self.cache_misses = 0
        self._proc: subprocess.Popen[str] | None = None
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._closed = False
        self._tail: deque[str] = deque(maxlen=12)
        self.engine_name = "Stockfish"
        self.audit = audit
        self._last_mode = ""
        self._last_lines: list[str] = []

        if self.network_path is not None and not Path(self.network_path).is_file():
            raise EvaluatorError(f"red Stockfish no encontrada: {self.network_path}")
        if not Path(self.engine_path).is_file():
            raise EvaluatorError(f"ejecutable Stockfish no encontrado: {self.engine_path}")

        self._start()

    @staticmethod
    def parse_final_evaluation(lines: list[str]) -> int | None:
        """Return White-perspective centipawns from Stockfish trace output."""
        for line in reversed(lines):
            match = _FINAL_RE.search(line)
            if match:
                # Stockfish prints the trace in pawn units (e.g. +0.37) and
                # explicitly from White's point of view.
                return int(round(float(match.group(1)) * 100.0))
        return None

    @staticmethod
    def parse_search_score(lines: list[str], side_to_move: chess.Color) -> int | None:
        """Return a UCI search score normalized to White perspective."""
        last: tuple[str, int] | None = None
        for line in lines:
            match = _SCORE_RE.search(line)
            if match:
                last = (match.group(1).lower(), int(match.group(2)))
        if last is None:
            return None
        kind, value = last
        if kind == "mate":
            # UCI mate N is from side-to-move perspective.  We only need the
            # sign for the evaluator contract; MATE_CP stays below search sentinels.
            stm_cp = MATE_CP if value > 0 else -MATE_CP
        else:
            stm_cp = int(value)
        return stm_cp if side_to_move == chess.WHITE else -stm_cp

    def _start(self) -> None:
        self._closed = False
        self._lines = queue.Queue()
        self._tail.clear()
        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW
        try:
            self._proc = subprocess.Popen(
                [self.engine_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                cwd=str(Path(self.engine_path).parent),
            )
        except OSError as exc:
            raise EvaluatorError(f"no se pudo iniciar Stockfish: {exc}") from exc

        self._reader = threading.Thread(target=self._reader_loop, daemon=True, name="stockfish-eval-reader")
        self._reader.start()

        self._send("uci")
        uci_lines = self._read_until(lambda s: s.strip() == "uciok", "uciok")
        for line in uci_lines:
            if line.startswith("id name "):
                self.engine_name = line[8:].strip() or self.engine_name
        if not any("option name EvalFile " in line for line in uci_lines):
            self.close()
            raise EvaluatorError("el ejecutable no expone la opción UCI EvalFile")

        # Keep this evaluator deterministic and light.  Threads/Hash matter only
        # for the exceptional in-check depth-1 fallback, not for `eval` itself.
        self._send("setoption name Threads value 1")
        self._send("setoption name Hash value 16")
        if self.network_path is not None:
            # An explicit --network overrides Stockfish's own default/embedded
            # EvalFile.  If it is omitted we deliberately leave EvalFile
            # untouched, so Stockfish evaluates with the network bundled with
            # (or otherwise selected by default in) that executable.
            self._send(f"setoption name EvalFile value {self.network_path}")
        self._send("isready")
        ready_desc = "readyok tras EvalFile" if self.network_path is not None else "readyok inicial"
        ready = self._read_until(lambda s: s.strip() == "readyok", ready_desc)
        joined = "\n".join(uci_lines + ready).lower()
        if self.audit is not None:
            self.audit.event(
                "stockfish_evaluator_startup",
                engine_path=self.engine_path, engine_name=self.engine_name, network_path=self.network_path,
                timeout_s=self.timeout_s, check_depth=self.check_depth, cache_size=self.cache_size,
                uci_lines=uci_lines, ready_lines=ready,
            )
        if self.network_path is not None and (
            "failed to load" in joined or ("error" in joined and "evalfile" in joined)
        ):
            self.close()
            raise EvaluatorError("Stockfish rechazó la red indicada en EvalFile")

    def _reader_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\r\n")
                self._tail.append(line)
                self._lines.put(line)
        finally:
            self._lines.put(None)

    def _send(self, command: str) -> None:
        proc = self._proc
        if self._closed or proc is None or proc.poll() is not None or proc.stdin is None:
            raise EvaluatorError("proceso Stockfish no disponible")
        try:
            proc.stdin.write(command + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise EvaluatorError(f"falló comunicación con Stockfish: {exc}") from exc

    def _read_until(self, predicate, description: str) -> list[str]:
        deadline = time.monotonic() + self.timeout_s
        out: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise EvaluatorError(f"timeout esperando {description} de Stockfish")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise EvaluatorError(f"timeout esperando {description} de Stockfish") from exc
            if line is None:
                code = None
                if self._proc is not None:
                    try:
                        code = self._proc.wait(timeout=0.25)
                    except subprocess.TimeoutExpired:
                        code = self._proc.poll()
                tail = " | ".join(self._tail) or "<sin salida>"
                raise EvaluatorError(
                    f"Stockfish terminó inesperadamente (exit={code}); últimas líneas: {tail}"
                )
            out.append(line)
            if predicate(line):
                return out

    def _eval_trace(self, board: chess.Board) -> int:
        self._send(f"position fen {board.fen()}")
        self._send("eval")
        # `eval` has no formal terminator.  `isready` provides a robust boundary
        # after all trace output has been emitted.
        self._send("isready")
        lines = self._read_until(lambda s: s.strip() == "readyok", "Final evaluation")
        self._last_mode = "eval"
        self._last_lines = list(lines)
        cp = self.parse_final_evaluation(lines)
        if cp is None:
            if any("Final evaluation: none (in check)" in line for line in lines):
                return self._eval_in_check(board)
            tail = " | ".join(lines[-5:])
            raise EvaluatorError(f"Stockfish no entregó Final evaluation; salida final: {tail}")
        return cp

    def _eval_in_check(self, board: chess.Board) -> int:
        """Heuristic only for non-terminal check positions.

        Stockfish's static `eval` intentionally refuses positions in check.
        A depth-1 (configurable) legal search resolves the check and reports the
        normal UCI score.  This path is exceptional and deliberately visible in
        the implementation; ordinary leaves always use Final evaluation.
        """
        self._send(f"position fen {board.fen()}")
        self._send(f"go depth {self.check_depth}")
        lines = self._read_until(lambda s: s.startswith("bestmove "), "bestmove de fallback en jaque")
        self._last_mode = f"check-search-depth-{self.check_depth}"
        self._last_lines = list(lines)
        cp = self.parse_search_score(lines, board.turn)
        if cp is None:
            tail = " | ".join(lines[-8:])
            raise EvaluatorError(f"Stockfish no entregó score en fallback de jaque; salida final: {tail}")
        return cp

    def _evaluate_once(self, board: chess.Board) -> int:
        if board.is_check():
            return self._eval_in_check(board)
        return self._eval_trace(board)


    @staticmethod
    def _cache_key(board: chess.Board) -> str:
        # Stockfish's static evaluation can be affected by the halfmove clock
        # (rule-50 scaling), so retain the first five FEN fields.  The fullmove
        # number is irrelevant to position evaluation and is intentionally omitted.
        return " ".join(board.fen().split()[:5])

    def _cache_get(self, key: str) -> int | None:
        if self.cache_size <= 0:
            return None
        try:
            value = self._cache.pop(key)
        except KeyError:
            return None
        self._cache[key] = value
        self.cache_hits += 1
        return value

    def _cache_put(self, key: str, value: int) -> None:
        if self.cache_size <= 0:
            return
        if key in self._cache:
            self._cache.pop(key, None)
        self._cache[key] = int(value)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def _restart_after_backend_loss(self) -> None:
        # A Stockfish subprocess may be killed by a transient backend/resource
        # failure.  Recreate it exactly once; repeated failure is surfaced.
        self.close()
        self._proc = None
        self._reader = None
        self._start()

    def evaluate(self, board: chess.Board) -> int:
        # Common evaluator contract: White-perspective centipawns.
        t0 = time.monotonic()
        fen = board.fen()
        # Terminal status is checked before cache lookup because claimable
        # repetition depends on move history and is not representable by FEN.
        if board.is_checkmate():
            cp = -MATE_CP if board.turn == chess.WHITE else MATE_CP
            if self.audit is not None:
                self.audit.evaluator_event(fen=fen, turn="white" if board.turn else "black", in_check=True, terminal="checkmate", score_white_cp=cp, elapsed_ms=0.0, mode="local-terminal", raw_lines=[])
            return cp
        if board.is_game_over(claim_draw=True):
            if self.audit is not None:
                self.audit.evaluator_event(fen=fen, turn="white" if board.turn else "black", in_check=board.is_check(), terminal="draw", score_white_cp=0, elapsed_ms=0.0, mode="local-terminal", raw_lines=[])
            return 0

        key = self._cache_key(board)
        cached = self._cache_get(key)
        if cached is not None:
            if self.audit is not None:
                self.audit.evaluator_event(
                    fen=fen, turn="white" if board.turn else "black", in_check=board.is_check(),
                    terminal=None, score_white_cp=cached, elapsed_ms=0.0,
                    mode="cache-hit", raw_lines=[],
                )
            return cached
        self.cache_misses += 1

        try:
            cp = self._evaluate_once(board)
            if self.audit is not None:
                self.audit.evaluator_event(
                    fen=fen, turn="white" if board.turn else "black", in_check=board.is_check(),
                    terminal=None, score_white_cp=cp, elapsed_ms=(time.monotonic()-t0)*1000.0,
                    mode=self._last_mode, raw_lines=self._last_lines,
                )
            self._cache_put(key, cp)
            return cp
        except EvaluatorError as exc:
            # Retry only when the backend really disappeared. Do not mask
            # protocol errors or timeouts with an unrelated restart.
            proc_dead = self._proc is None or self._proc.poll() is not None
            if not proc_dead:
                raise
            first_error = str(exc)
            self._restart_after_backend_loss()
            try:
                cp = self._evaluate_once(board)
                if self.audit is not None:
                    self.audit.evaluator_event(
                        fen=fen, turn="white" if board.turn else "black", in_check=board.is_check(),
                        terminal=None, score_white_cp=cp, elapsed_ms=(time.monotonic()-t0)*1000.0,
                        mode=self._last_mode + "-after-restart", raw_lines=self._last_lines,
                    )
                self._cache_put(key, cp)
                return cp
            except EvaluatorError as retry_exc:
                raise EvaluatorError(
                    f"Stockfish falló tras un reinicio; primer error: {first_error}; "
                    f"segundo error: {retry_exc}"
                ) from retry_exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.poll() is None and proc.stdin is not None:
                proc.stdin.write("quit\n")
                proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except OSError:
            pass
        try:
            if proc.stdout is not None:
                proc.stdout.close()
        except OSError:
            pass
