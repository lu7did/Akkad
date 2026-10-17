from __future__ import annotations

import time
import threading
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chess
import chess.engine

from .sargon import SargonEngine, SearchTimeout


class BrainTimeout(TimeoutError):
    """Raised when a Challenger brain exhausts the time available for a move."""


@dataclass(slots=True)
class BrainResult:
    move: chess.Move
    elapsed: float
    score: float | None = None
    nodes: int | None = None


class Brain(Protocol):
    name: str

    def new_game(self) -> None: ...

    def choose(
        self,
        board: chess.Board,
        *,
        deadline: float | None = None,
        challenger_clock: float | None = None,
        opponent_clock: float | None = None,
        challenger_color: chess.Color | None = None,
    ) -> BrainResult: ...

    def close(self) -> None: ...


class SargonBrain:
    """Adapter for Challenger's algorithmic SARGON 1978 approximation."""

    name = "sargon"

    def __init__(self, plies: int, qdepth: int = 0, seed: int | None = None):
        self.engine = SargonEngine(plies, qdepth=qdepth, seed=seed)

    def new_game(self) -> None:
        # Sargon is stateless between games.
        return None

    def choose(
        self,
        board: chess.Board,
        *,
        deadline: float | None = None,
        challenger_clock: float | None = None,
        opponent_clock: float | None = None,
        challenger_color: chess.Color | None = None,
    ) -> BrainResult:
        try:
            result = self.engine.choose(board, deadline=deadline)
        except SearchTimeout as exc:
            raise BrainTimeout(str(exc)) from exc
        return BrainResult(
            move=result.move,
            elapsed=result.elapsed,
            score=result.score,
            nodes=result.nodes,
        )

    def close(self) -> None:
        return None


class RandomBrain:
    """Reference brain that chooses uniformly among the current legal moves."""

    name = "random"

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def new_game(self) -> None:
        return None

    def choose(
        self,
        board: chess.Board,
        *,
        deadline: float | None = None,
        challenger_clock: float | None = None,
        opponent_clock: float | None = None,
        challenger_color: chess.Color | None = None,
    ) -> BrainResult:
        if deadline is not None and time.monotonic() >= deadline:
            raise BrainTimeout("Random agotó su tiempo de juego")
        start = time.monotonic()
        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No hay movimientos legales")
        move = self.rng.choice(legal)
        return BrainResult(move=move, elapsed=time.monotonic() - start)

    def close(self) -> None:
        return None


class HumanBrain:
    """Human move-selection brain driven by GUI square clicks.

    The GUI never mutates the game board.  During ``choose()`` this brain keeps
    an isolated snapshot of the current position, accepts square selections
    from the Tk thread, validates them with python-chess and returns a legal
    move to ChallengerRunner.  The controller remains authoritative for the
    real board, clocks, UCI connection, PGN and terminal rules.
    """

    name = "human"

    def __init__(self):
        self._cond = threading.Condition()
        self._board: chess.Board | None = None
        self._selected: chess.Square | None = None
        self._move: chess.Move | None = None
        self._waiting = False
        self._closed = False
        self._message = "Esperando turno"

    def new_game(self) -> None:
        with self._cond:
            self._board = None
            self._selected = None
            self._move = None
            self._waiting = False
            self._closed = False
            self._message = "Esperando turno"
            self._cond.notify_all()

    def choose(
        self,
        board: chess.Board,
        *,
        deadline: float | None = None,
        challenger_clock: float | None = None,
        opponent_clock: float | None = None,
        challenger_color: chess.Color | None = None,
    ) -> BrainResult:
        start = time.monotonic()
        with self._cond:
            self._board = board.copy(stack=True)
            self._selected = None
            self._move = None
            self._waiting = True
            self._message = "Seleccione una pieza"
            self._cond.notify_all()

            while self._move is None:
                if self._closed:
                    self._waiting = False
                    self._board = None
                    self._selected = None
                    raise BrainTimeout("El brain humano fue cerrado")
                if deadline is None:
                    self._cond.wait(timeout=0.25)
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._waiting = False
                        self._board = None
                        self._selected = None
                        self._message = "Tiempo agotado"
                        raise BrainTimeout("El jugador humano agotó su tiempo de juego")
                    self._cond.wait(timeout=min(0.25, remaining))

            move = self._move
            self._move = None
            self._selected = None
            self._waiting = False
            self._board = None
            self._message = "Jugada aceptada"
            return BrainResult(move=move, elapsed=time.monotonic() - start)

    def click_square(self, square: chess.Square) -> bool:
        """Consumes one GUI click. Returns True when the visual state changed."""
        with self._cond:
            board = self._board
            if not self._waiting or board is None:
                self._message = "No es el turno de Challenger"
                return False

            piece = board.piece_at(square)
            if self._selected is None:
                if piece is None:
                    self._message = "Seleccione una pieza propia"
                    return False
                if piece.color != board.turn:
                    self._message = "Esa pieza pertenece al rival"
                    return False
                self._selected = square
                self._message = f"Seleccionada {chess.square_name(square)}"
                return True

            # Clicking another own piece simply changes the active selection.
            if piece is not None and piece.color == board.turn:
                self._selected = square
                self._message = f"Seleccionada {chess.square_name(square)}"
                return True

            source = self._selected
            candidates = [
                move for move in board.legal_moves
                if move.from_square == source and move.to_square == square
            ]
            if not candidates:
                self._message = f"Jugada ilegal: {chess.square_name(source)}-{chess.square_name(square)}"
                return True

            # Promotion has several legal moves with identical source/destination.
            # With a two-click UI we choose the standard queen promotion.
            move = next((m for m in candidates if m.promotion == chess.QUEEN), candidates[0])
            self._move = move
            self._selected = None
            self._message = f"Jugada {move.uci()}"
            self._cond.notify_all()
            return True

    def selected_square(self) -> chess.Square | None:
        with self._cond:
            return self._selected

    def status_message(self) -> str:
        with self._cond:
            return self._message

    def is_waiting(self) -> bool:
        with self._cond:
            return self._waiting

    def close(self) -> None:
        with self._cond:
            self._waiting = False
            self._closed = True
            self._board = None
            self._selected = None
            self._move = None
            self._cond.notify_all()


class StockfishBrain:
    """External Stockfish process used only as Challenger's move-selection brain.

    Challenger remains authoritative for clocks, legality, GUI state, terminal
    rules, PGN logging, result reporting and persistence. Stockfish receives the
    current board and clock state and returns a best move through standard UCI.
    """

    name = "stockfish"

    def __init__(self, executable: str, timeout_ms: int = 120000, movetime_ms: int = 2000):
        path = Path(executable).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"No se encontró Stockfish: {path}")
        self.executable = str(path)
        self.timeout_seconds = max(0.001, float(timeout_ms) / 1000.0)
        self.movetime_seconds = max(0.001, float(movetime_ms) / 1000.0)
        self.engine = chess.engine.SimpleEngine.popen_uci(self.executable, timeout=self.timeout_seconds)
        self._game_token: object = object()

    def new_game(self) -> None:
        # python-chess sends ucinewgame when the game token changes.
        self._game_token = object()

    def choose(
        self,
        board: chess.Board,
        *,
        deadline: float | None = None,
        challenger_clock: float | None = None,
        opponent_clock: float | None = None,
        challenger_color: chess.Color | None = None,
    ) -> BrainResult:
        if challenger_clock is None or opponent_clock is None or challenger_color is None:
            raise ValueError("StockfishBrain requiere ambos relojes y el color de Challenger")

        white_clock = challenger_clock if challenger_color == chess.WHITE else opponent_clock
        black_clock = challenger_clock if challenger_color == chess.BLACK else opponent_clock
        # Stockfish must not be allowed to consume an arbitrary fraction of the
        # whole Challenger game clock.  The external engine is a move-selection
        # brain, while Challenger owns time management.  Send the real clocks
        # for context, but also a hard per-move ``movetime`` cap.
        remaining = max(0.001, challenger_clock)
        move_cap = min(self.movetime_seconds, remaining)
        if deadline is not None:
            move_cap = min(move_cap, max(0.001, deadline - time.monotonic()))
        limit = chess.engine.Limit(
            time=move_cap,
            white_clock=max(0.0, white_clock),
            black_clock=max(0.0, black_clock),
            white_inc=0.0,
            black_inc=0.0,
        )
        start = time.monotonic()
        try:
            result = self.engine.play(board, limit, game=self._game_token)
        except TimeoutError as exc:
            if deadline is not None and time.monotonic() >= deadline:
                raise BrainTimeout("Stockfish agotó su tiempo de juego") from exc
            raise RuntimeError(f"Stockfish excedió el timeout UCI interno: {exc}") from exc
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError) as exc:
            raise RuntimeError(f"Stockfish falló al calcular la jugada: {exc}") from exc
        elapsed = time.monotonic() - start

        # Challenger owns the hard chess clock. Even if an external engine returns
        # late, the controller will convert the consumed time into a flag fall.
        if deadline is not None and time.monotonic() >= deadline:
            raise BrainTimeout("Stockfish agotó su tiempo de juego")
        if result.move is None:
            raise RuntimeError("Stockfish no devolvió bestmove")
        return BrainResult(move=result.move, elapsed=elapsed)

    def close(self) -> None:
        try:
            self.engine.quit()
        except Exception:
            try:
                self.engine.close()
            except Exception:
                pass


def make_brain(args) -> Brain:
    name = str(getattr(args, "brain", "sargon")).lower()
    if name == "sargon":
        return SargonBrain(args.plies, qdepth=getattr(args, "qdepth", 0), seed=getattr(args, "seed", None))
    if name == "random":
        return RandomBrain(seed=getattr(args, "seed", None))
    if name == "human":
        return HumanBrain()
    if name == "stockfish":
        executable = getattr(args, "stockfish", None)
        if not executable:
            raise ValueError("--brain stockfish requiere --stockfish RUTA_AL_EJECUTABLE")
        return StockfishBrain(
            executable,
            timeout_ms=getattr(args, "timeout", 120000),
            movetime_ms=getattr(args, "stockfish_movetime", 2000),
        )
    raise ValueError(f"Brain desconocido: {name}")
