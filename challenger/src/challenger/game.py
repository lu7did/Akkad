from __future__ import annotations

import random
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Callable

import chess

from .brain import BrainTimeout, make_brain
from . import __version__
from .persistence import JsonHistory, Stats, format_stats, new_game_id
from .pgnlog import append_game
from .uci_client import TCPUCIClient, UCIError


@dataclass(slots=True)
class GameResult:
    outcome: str  # win/draw/loss from Challenger perspective
    token: str    # 1-0 / 0-1 / 1/2-1/2
    reason: str
    challenger_color: str = ""


@dataclass(slots=True)
class GameState:
    board: chess.Board
    challenger_color: chess.Color
    challenger_clock: float
    opponent_clock: float
    last_challenger: str = "-"
    last_opponent: str = "-"
    started_at: float = 0.0
    connected: bool = False
    active_color: chess.Color | None = None
    turn_started_at: float | None = None


StateCallback = Callable[[GameState], None]
ResultCallback = Callable[[GameResult], None]


class ChallengerRunner:
    def __init__(self, args, state_callback: StateCallback | None = None, result_callback: ResultCallback | None = None):
        self.args = args
        self.state_callback = state_callback
        self.result_callback = result_callback
        self.brain = make_brain(args)
        self.client = self._make_client()
        self.journal = JsonHistory(getattr(args, "json", None))
        self.history = self.journal.global_stats
        self.session = Stats()
        self.rng = random.Random(getattr(args, "seed", None))

    def _make_client(self) -> TCPUCIClient:
        return TCPUCIClient(
            self.args.ip,
            self.args.port,
            timeout_ms=self.args.timeout,
            verbose=False,
        )

    def _recover_uci_connection(self) -> None:
        # A timed-out UCI stream can still contain a late reply.  Reusing that
        # stream risks associating stale output with the next game, so recovery
        # always starts from a fresh TCP/UCI session.
        try:
            self.client.close()
        except Exception:
            pass
        self.client = self._make_client()
        self.connect()

    def _pick_color(self) -> chess.Color:
        if self.args.color == "white": return chess.WHITE
        if self.args.color == "black": return chess.BLACK
        return self.rng.choice([chess.WHITE, chess.BLACK])

    def _emit(self, state: GameState) -> None:
        if self.state_callback:
            # Emit an immutable-in-practice snapshot so the GUI never observes
            # a GameState while the worker thread is mutating it for the next ply.
            self.state_callback(GameState(
                board=state.board.copy(stack=True),
                challenger_color=state.challenger_color,
                challenger_clock=state.challenger_clock,
                opponent_clock=state.opponent_clock,
                last_challenger=state.last_challenger,
                last_opponent=state.last_opponent,
                started_at=state.started_at,
                connected=state.connected,
                active_color=state.active_color,
                turn_started_at=state.turn_started_at,
            ))

    @staticmethod
    def _result_from_board(board: chess.Board, challenger_color: chess.Color) -> GameResult:
        outcome = board.outcome(claim_draw=True)
        if outcome is None:
            raise RuntimeError("La partida no terminó")
        reason = outcome.termination.name
        token = outcome.result()
        color_name = "white" if challenger_color == chess.WHITE else "black"
        if outcome.winner is None: return GameResult("draw", token, reason, color_name)
        return GameResult("win" if outcome.winner == challenger_color else "loss", token, reason, color_name)

    @staticmethod
    def _result_by_timeout(board: chess.Board, challenger_won: bool, challenger_color: chess.Color) -> GameResult:
        # Challenger uses a strict flag-fall rule: reaching zero loses,
        # independently of the remaining material on the board.
        winner = challenger_color if challenger_won else not challenger_color
        token = "1-0" if winner == chess.WHITE else "0-1"
        color_name = "white" if challenger_color == chess.WHITE else "black"
        return GameResult("win" if challenger_won else "loss", token, "TIMEOUT", color_name)

    def _verbose_move(self, who: str, board: chess.Board, move: chess.Move, elapsed: float) -> None:
        if not self.args.verbose: return
        try: san = board.san(move)
        except Exception: san = move.uci()
        print(f"[{who}] {san} ({move.uci()}) | {elapsed:.3f}s")

    def connect(self) -> None:
        self.client.connect()
        if self.args.verbose:
            print(f"Conectado a {self.client.id_name} en {self.args.ip}:{self.args.port}")

    def play_one(self) -> GameResult:
        color = self._pick_color()
        board = chess.Board()
        total_seconds = float(self.args.gametime) * 60.0
        challenger_clock = total_seconds
        opponent_clock = total_seconds
        moves: list[str] = []
        # Protocol setup is outside the chess clock. Both clocks start at their
        # full --gametime only after the UCI peer is ready for the new game.
        self.client.new_game()
        self.brain.new_game()
        game_started = time.monotonic()
        game_started_wall = datetime.now().astimezone().isoformat(timespec="seconds")
        state = GameState(
            board.copy(stack=True), color, challenger_clock, opponent_clock,
            started_at=game_started, connected=True,
            active_color=board.turn, turn_started_at=game_started,
        )
        self._emit(state)

        while not board.is_game_over(claim_draw=True):
            # A legal move transfers the running clock to the opponent.  The
            # snapshot below marks the exact instant at which this turn starts.
            turn_start = time.monotonic()
            state.board = board.copy(stack=True)
            state.challenger_clock = max(0.0, challenger_clock)
            state.opponent_clock = max(0.0, opponent_clock)
            state.active_color = board.turn
            state.turn_started_at = turn_start
            self._emit(state)

            if board.turn == color:
                deadline = turn_start + challenger_clock
                try:
                    result = self.brain.choose(
                        board,
                        deadline=deadline,
                        challenger_clock=challenger_clock,
                        opponent_clock=opponent_clock,
                        challenger_color=color,
                    )
                except BrainTimeout:
                    challenger_clock = 0.0
                    final = self._result_by_timeout(board, False, color)
                    break
                elapsed = time.monotonic() - turn_start
                challenger_clock = max(0.0, challenger_clock - elapsed)
                if challenger_clock <= 0.0:
                    final = self._result_by_timeout(board, False, color)
                    break
                if result.move not in board.legal_moves:
                    raise RuntimeError(f"El brain {self.brain.name} produjo una jugada ilegal: {result.move.uci()}")
                self._verbose_move("CHALLENGER", board, result.move, elapsed)
                state.last_challenger = board.san(result.move)
                board.push(result.move)
                moves.append(result.move.uci())
            else:
                self.client.position(moves)
                # The UCI watchdog and the chess clock are independent.  We
                # wait until the first of them expires.  A watchdog timeout
                # invalidates this game; a genuine flag fall is a chess result.
                protocol_timeout = self.client.timeout_seconds
                wait_limit = min(opponent_clock, protocol_timeout)
                try:
                    best = self.client.go(
                        int(challenger_clock * 1000) if color == chess.WHITE else int(opponent_clock * 1000),
                        int(opponent_clock * 1000) if color == chess.WHITE else int(challenger_clock * 1000),
                        response_timeout=wait_limit,
                    )
                except TimeoutError:
                    elapsed = time.monotonic() - turn_start
                    opponent_clock = max(0.0, opponent_clock - elapsed)
                    self.client.stop()
                    if opponent_clock <= 0.0:
                        final = self._result_by_timeout(board, True, color)
                        break
                    raise TimeoutError(
                        f"Timeout UCI tras {self.args.timeout} ms esperando bestmove; "
                        f"la partida se descarta (quedaban {opponent_clock:.3f}s en el reloj rival)"
                    )
                elapsed = time.monotonic() - turn_start
                opponent_clock = max(0.0, opponent_clock - elapsed)
                if opponent_clock <= 0.0:
                    self.client.stop()
                    final = self._result_by_timeout(board, True, color)
                    break
                if best.move in {"0000", "(none)", "none"}:
                    if board.is_game_over(claim_draw=True):
                        final = self._result_from_board(board, color)
                        break
                    raise UCIError("El contrincante devolvió bestmove 0000 en una posición no terminal")
                try:
                    move = chess.Move.from_uci(best.move)
                except ValueError as exc:
                    raise UCIError(f"bestmove UCI inválido: {best.move}") from exc
                if move not in board.legal_moves:
                    raise UCIError(f"El contrincante devolvió una jugada ilegal: {best.move}")
                self._verbose_move("OPONENTE", board, move, elapsed)
                state.last_opponent = board.san(move)
                board.push(move)
                moves.append(move.uci())

            # The move is legal and complete: freeze the mover's consumed time
            # and start the opponent's clock immediately.
            state.board = board.copy(stack=True)
            state.challenger_clock = max(0.0, challenger_clock)
            state.opponent_clock = max(0.0, opponent_clock)
            state.active_color = board.turn
            state.turn_started_at = time.monotonic()
            self._emit(state)
        else:
            final = self._result_from_board(board, color)

        # Freeze both clocks at the terminal position.
        state.board = board.copy(stack=True)
        state.challenger_clock = max(0.0, challenger_clock)
        state.opponent_clock = max(0.0, opponent_clock)
        state.active_color = None
        state.turn_started_at = None
        self._emit(state)

        if getattr(self.args, "pgn", None):
            append_game(
                self.args.pgn,
                board,
                color,
                final.token,
                getattr(self.args, "evento", "Trainning run"),
            )
            if self.args.verbose:
                print(f"[PGN] Partida agregada a {self.args.pgn}")

        self.client.report_result_if_supported(final.token, final.reason)
        # Sincroniza el cierre antes de que --forever pueda comenzar otra partida.
        try: self.client.isready()
        except Exception: pass

        finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
        duration_seconds = time.monotonic() - game_started
        game_id = new_game_id()
        execution_arguments = {k: v for k, v in vars(self.args).items()}
        self.journal.record_game(
            event=getattr(self.args, "evento", "Trainning run"),
            game_id=game_id,
            outcome=final.outcome,
            token=final.token,
            reason=final.reason,
            challenger_color=final.challenger_color,
            finished_at=finished_at,
            event_started_at=game_started_wall,
            brain=self.brain.name,
            challenger_version=__version__,
            execution_arguments=execution_arguments,
            move_count=(len(moves) + 1) // 2,
            duration_seconds=duration_seconds,
            opponent_id=self.client.id_name or "unknown",
        )
        self.history = self.journal.global_stats
        self.session.add(final.outcome, brain=self.brain.name, token=final.token, reason=final.reason)
        print(f"Resultado: {final.token} | Challenger={final.outcome} | color={final.challenger_color} | motivo={final.reason} | brain={self.brain.name} | id={game_id}")
        print(format_stats("Histórico", self.history))
        print(format_stats("Ejecución", self.session))
        state.connected = self.client.connected
        self._emit(state)
        if self.result_callback:
            self.result_callback(final)
        return final

    def _retry_delay(self) -> None:
        for _ in range(100):
            time.sleep(0.1)

    def run(self) -> None:
        try:
            connected = False
            completed = 0
            target = None if self.args.forever else (self.args.run if self.args.run is not None else 1)
            retry_mode = self.args.forever or self.args.run is not None
            while target is None or completed < target:
                if not connected:
                    try:
                        self.connect()
                        connected = True
                    except TimeoutError as exc:
                        print(f"[UCI] {exc}")
                        if not retry_mode:
                            return
                        mode = "--forever" if self.args.forever else f"--run {self.args.run}"
                        print(f"[UCI] {mode} activo: reintento de conexión en 10 segundos.")
                        try:
                            self.client.close()
                        except Exception:
                            pass
                        self.client = self._make_client()
                        self._retry_delay()
                        continue

                try:
                    result = self.play_one()
                except TimeoutError as exc:
                    # Protocol failure: there is deliberately no PGN, no result
                    # notification and no statistics update for this attempt.
                    print(f"[UCI] {exc}")
                    print("[UCI] Partida descartada: no se contabiliza.")
                    if not retry_mode:
                        return
                    mode = "--forever" if self.args.forever else f"--run {self.args.run}"
                    print(f"[UCI] {mode} activo: nueva partida en 10 segundos; el intento descartado no consume el cupo.")
                    self._retry_delay()
                    try:
                        self._recover_uci_connection()
                        connected = True
                    except (TimeoutError, UCIError, OSError) as reconnect_exc:
                        print(f"[UCI] Reconexión fallida: {reconnect_exc}")
                        try:
                            self.client.close()
                        except Exception:
                            pass
                        self.client = self._make_client()
                        connected = False
                    continue

                completed += 1
                if self.args.verbose:
                    print(f"[PARTIDA] finalizada: {result.token} | motivo={result.reason} | {completed}/{target if target is not None else '∞'}")
                if target is not None and completed >= target:
                    return
                self._retry_delay()
        finally:
            self.client.close()
            self.brain.close()
