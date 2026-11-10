from __future__ import annotations

import argparse
import os
import shlex
import ctypes
from ctypes import wintypes
import sys

import chess
from tkinter import messagebox

from . import __version__
from .game import ChallengerRunner
from .gui import ChallengerGUI
from .persistence import stats_path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="challenger", description="Challenger: jugador con brains intercambiables contra un motor UCI TCP o stdio")
    p.add_argument("--ip", default="127.0.0.1", help="IP del motor UCI contrincante (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=6110, help="Puerto TCP UCI (default: 6110)")
    p.add_argument("--uci-engine", metavar="EJECUTABLE", default=None,
                   help="Motor local UCI por stdin/stdout; sustituye --ip/--port")
    p.add_argument("--uci-args", metavar="CADENA", default=None,
                   help="Cadena de argumentos del motor UCI local; respeta comillas y espacios")
    p.add_argument("--FEN", "--fen", dest="fen", metavar="FEN", default=None,
                   help="Posición inicial en notación FEN completa (se valida antes de conectar)")
    p.add_argument("--color", choices=["white","black","random"], default="random", help="Color de Challenger; random por defecto")
    p.add_argument("--brain", type=str.lower, choices=["sargon", "random", "stockfish", "human"], default="sargon", help="Motor de decisión de Challenger: sargon, random, stockfish o human (default: sargon)")
    p.add_argument("--stockfish", metavar="RUTA", help="Ruta al ejecutable Stockfish; requerida con --brain stockfish")
    p.add_argument("--stockfish-movetime", type=int, default=2000, metavar="MS",
                   help="Tiempo máximo de cálculo de Stockfish por jugada en ms (default: 2000)")
    p.add_argument("--plies", type=int, default=2, help="Profundidad Sargon en plies (default: 2; ignorada por Random, Stockfish y Human)")
    p.add_argument("--qdepth", type=int, default=0, help="Sargon histórico: debe ser 0 (sin quiescence); ignorado por Random, Stockfish y Human")
    p.add_argument("--verbose", action="store_true", help="Muestra jugadas y tiempos")
    p.add_argument("--gui", action="store_true", help="Muestra tablero gráfico")
    p.add_argument("--monitor", metavar="HOST:PORT", default=None,
                   help="Observa un stream UCI TCP en un tablero; no juega")
    p.add_argument("--forever", action="store_true", help="Juega repetidamente, esperando 10 segundos entre partidas")
    p.add_argument("--run", type=int, metavar="N", help="Juega N partidas (1..999); >999 equivale a --forever")
    p.add_argument("--pgn", metavar="ARCHIVO", help="Acumula cada partida terminada en este archivo PGN")
    p.add_argument("--evento", "--event", dest="evento", default="Trainning run", help='Evento lógico/PGN (default: "Trainning run"); --event se conserva como alias')
    p.add_argument("--json", metavar="ARCHIVO", default=None, help="Archivo JSON de historial (default: challenger.json junto a la aplicación)")
    p.add_argument("--gametime", type=float, default=30.0, help="Tiempo total por jugador en minutos (default: 30)")
    p.add_argument("--timeout", type=int, default=120000, metavar="MS",
                   help="Timeout máximo para una respuesta UCI en milisegundos (default: 120000)")
    p.add_argument("--seed", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--version", action="version", version=f"challenger {__version__}")
    return p


def _modal_result(text: str) -> None:
    try:
        messagebox.showinfo("Challenger", text)
    except Exception:
        pass


def _print_arguments(args) -> None:
    print("[CHALLENGER] Argumentos efectivos:", file=sys.stderr)
    for key, value in sorted(vars(args).items()):
        print(f"  --{key.replace('_', '-')}: {value}", file=sys.stderr)


def split_uci_args(command_line: str) -> list[str]:
    """Parse one argument string with native quoting (without invoking a shell).

    On Windows CommandLineToArgvW matches ordinary Windows command-line quoting;
    on POSIX shlex handles single/double quotes and backslash escaping.
    """
    if os.name != "nt":
        return shlex.split(command_line, posix=True)
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32
    parse = shell32.CommandLineToArgvW
    parse.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int(0)
    # Prefix a dummy program name so even a leading quoted argument is parsed
    # as an argument, with no special treatment of argv[0].
    ptr = parse('challenger.exe ' + command_line, ctypes.byref(count))
    if not ptr:
        raise ValueError("No fue posible interpretar --uci-args")
    try:
        return [ptr[i] for i in range(1, count.value)]
    finally:
        kernel32.LocalFree(ctypes.cast(ptr, ctypes.c_void_p))


def main(argv: list[str] | None = None) -> int:
    # Ensure redirected stderr is UTF-8 too. Windows consoles use Python's
    # Unicode console writer; child UTF-8 diagnostics are decoded in the relay.
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parser().parse_args(argv)
    if args.uci_args is not None and args.uci_engine is None:
        parser().error("--uci-args requiere --uci-engine")
    if args.uci_engine is not None and not args.uci_engine.strip():
        parser().error("--uci-engine no puede estar vacío")
    try:
        args.uci_argv = split_uci_args(args.uci_args or "")
    except ValueError as exc:
        parser().error(f"--uci-args: {exc}")
    if args.monitor is not None and args.uci_engine is not None:
        parser().error("--monitor y --uci-engine son mutuamente excluyentes")
    if args.monitor is not None:
        from .monitor import MonitorGUI, parse_endpoint
        try:
            host, port = parse_endpoint(args.monitor)
        except ValueError as exc:
            parser().error(f"--monitor: {exc}")
        try:
            MonitorGUI(host, port).run()
            return 0
        except (KeyboardInterrupt, Exception) as exc:
            print(f"challenger monitor: {exc}", file=sys.stderr)
            return 2
    if args.fen is not None:
        try:
            initial = chess.Board(args.fen)
            if initial.status() != chess.STATUS_VALID:
                raise ValueError(f"posición ilegal (status={initial.status()})")
            args.fen = initial.fen()  # Normalización y validación antes de conectar / abrir GUI
        except (ValueError, TypeError) as exc:
            parser().error(f"--FEN inválido: {exc}")
    if args.run is not None and args.run < 1:
        parser().error("--run debe ser >= 1")
    if args.forever and args.run is not None:
        print("[CHALLENGER] --forever tiene prioridad; se ignora --run.", file=sys.stderr)
        args.run = None
    elif args.run is not None and args.run > 999:
        print(f"[CHALLENGER] --run {args.run} excede 999; se ignora y se activa comportamiento --forever.", file=sys.stderr)
        args.run = None
        args.forever = True
    if args.json is None:
        args.json = str(stats_path())
    if args.plies < 1:
        parser().error("--plies debe ser >= 1")
    if args.qdepth != 0 and args.brain == "sargon":
        parser().error("--qdepth debe ser 0 para el brain Sargon (sin quiescence)")
    if args.qdepth < 0:
        parser().error("--qdepth debe ser >= 0")
    if args.brain == "human" and not args.gui:
        parser().error("--brain human requiere --gui")
    if args.brain == "stockfish" and not args.stockfish:
        parser().error("--brain stockfish requiere --stockfish RUTA_AL_EJECUTABLE")
    if args.stockfish_movetime <= 0:
        parser().error("--stockfish-movetime debe ser > 0 milisegundos")
    if args.gametime <= 0:
        parser().error("--gametime debe ser > 0")
    if not 1 <= args.port <= 65535:
        parser().error("--port debe estar entre 1 y 65535")
    if args.timeout <= 0:
        parser().error("--timeout debe ser > 0 milisegundos")
    _print_arguments(args)
    try:
        if args.gui:
            ChallengerGUI(args).run()
        else:
            runner = ChallengerRunner(args)
            runner.run()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"challenger: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
