#!/usr/bin/env python3
"""Prueba sencilla de un motor UCI (incluye searchmoves y MultiPV)."""
import argparse
import subprocess
import time


def wait_for(proc, expected, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError(f"Motor cerrado esperando {expected}")
        line = line.strip()
        print("<", line)
        if line == expected:
            return
    raise TimeoutError(expected)


def send(proc, command):
    print(">", command)
    proc.stdin.write(command + "\n")
    proc.stdin.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", help="Ruta del motor UCI .exe")
    ap.add_argument("--fen", default="startpos", help="FEN o 'startpos'")
    ap.add_argument("--moves", nargs="*", default=[], help="Jugadas UCI a analizar (searchmoves)")
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--qdepth", type=int, default=2)
    ap.add_argument("--movetime", type=int, default=5000, help="Tiempo máximo en ms")
    args = ap.parse_args()

    # Este ejemplo se orienta a picoSargon x86, que acepta go qdepth N.
    proc = subprocess.Popen([args.exe], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, bufsize=1)
    try:
        send(proc, "uci")
        wait_for(proc, "uciok", 30)
        send(proc, "isready")
        wait_for(proc, "readyok", 30)
        send(proc, "position startpos" if args.fen == "startpos" else "position fen " + args.fen)
        go = f"go depth {args.depth} qdepth {args.qdepth} movetime {args.movetime}"
        if args.moves:
            go += " searchmoves " + " ".join(args.moves)
        send(proc, go)
        start = time.monotonic()
        bestmove = None
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("Motor terminó sin bestmove")
            line = line.strip()
            print("<", line)
            if line.startswith("bestmove "):
                bestmove = line.split()[1]
                break
        print(f"\nRESULTADO: bestmove={bestmove}, tiempo_pared={(time.monotonic()-start)*1000:.0f} ms")
    finally:
        if proc.poll() is None:
            send(proc, "quit")
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
