from __future__ import annotations

import argparse
import sys
from tkinter import messagebox

from . import __version__
from .game import ChallengerRunner
from .gui import ChallengerGUI
from .persistence import stats_path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="challenger", description="Challenger: jugador de ajedrez con brains intercambiables contra un motor UCI TCP")
    p.add_argument("--ip", default="127.0.0.1", help="IP del motor UCI contrincante (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=6110, help="Puerto TCP UCI (default: 6110)")
    p.add_argument("--color", choices=["white","black","random"], default="random", help="Color de Challenger; random por defecto")
    p.add_argument("--brain", type=str.lower, choices=["sargon", "random", "stockfish", "human"], default="sargon", help="Motor de decisión de Challenger: sargon, random, stockfish o human (default: sargon)")
    p.add_argument("--stockfish", metavar="RUTA", help="Ruta al ejecutable Stockfish; requerida con --brain stockfish")
    p.add_argument("--stockfish-movetime", type=int, default=2000, metavar="MS",
                   help="Tiempo máximo de cálculo de Stockfish por jugada en ms (default: 2000)")
    p.add_argument("--plies", type=int, default=2, help="Profundidad Sargon en plies (default: 2; ignorada por Random, Stockfish y Human)")
    p.add_argument("--qdepth", type=int, default=0, help="Sargon histórico: debe ser 0 (sin quiescence); ignorado por Random, Stockfish y Human")
    p.add_argument("--verbose", action="store_true", help="Muestra jugadas y tiempos")
    p.add_argument("--gui", action="store_true", help="Muestra tablero gráfico")
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
    print("[CHALLENGER] Argumentos efectivos:")
    for key, value in sorted(vars(args).items()):
        print(f"  --{key.replace('_', '-')}: {value}")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.run is not None and args.run < 1:
        parser().error("--run debe ser >= 1")
    if args.forever and args.run is not None:
        print("[CHALLENGER] --forever tiene prioridad; se ignora --run.")
        args.run = None
    elif args.run is not None and args.run > 999:
        print(f"[CHALLENGER] --run {args.run} excede 999; se ignora y se activa comportamiento --forever.")
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
