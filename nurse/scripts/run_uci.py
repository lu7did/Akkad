#!/usr/bin/env python3
"""Ejecuta un motor UCI y prueba go/searchmoves.

--args contiene los argumentos de arranque del motor, con comillas para rutas con espacios.
Las opciones --depth/--qdepth/--movetime son parámetros del comando UCI go.
"""
import argparse
import shlex
import os
import subprocess
import sys
import time
import threading


def send(proc, command):
    if proc.poll() is not None:
        raise RuntimeError(f"Motor terminó (exitcode={proc.returncode}) antes de {command!r}")
    print(">", command, flush=True)
    try:
        proc.stdin.write(command + "\n")
        proc.stdin.flush()
    except (OSError, BrokenPipeError, ValueError) as exc:
        raise RuntimeError(f"No se pudo enviar {command!r}: motor cerrado") from exc


def receive(proc):
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError(f"Motor cerró stdout (exitcode={proc.poll()}); revise sus argumentos y stderr")
    line = line.strip()
    print("<", line, flush=True)
    return line


def until(proc, expected):
    while receive(proc) != expected:
        pass


def forward_stderr(proc):
    """Decodifica el stderr UTF-8 del motor antes de mostrarlo en Windows."""
    try:
        for line in proc.stderr:
            print(line, end="", file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass


def main():
    argv = sys.argv[1:]
    # '--' separa argumentos del script y argumentos del ejecutable.
    if "--" in argv:
        pos = argv.index("--")
        script_argv, engine_argv = argv[:pos], argv[pos + 1:]
    else:
        script_argv, engine_argv = argv, []

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("exe", help="Ruta del ejecutable UCI")
    ap.add_argument("--fen", default="startpos", help="FEN o startpos")
    ap.add_argument("--moves", nargs="*", default=[], help="Movidas UCI permitidas")
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--qdepth", type=int, default=2)
    ap.add_argument("--movetime", type=int, default=5000, help="Milisegundos")
    ap.add_argument("--args", default="", metavar="TEXTO",
                    help="Argumentos transparentes del ejecutable; ej. --args '--cores 4 --weights red.bin'")
    ap.add_argument("--weights", help="Compatibilidad: argumento --weights del motor")
    ap.add_argument("--brains", help="Compatibilidad: argumento --brains del motor")
    args = ap.parse_args(script_argv)

    cmd = [args.exe]
    if args.weights:
        cmd += ["--weights", args.weights]
    if args.brains:
        cmd += ["--brains", args.brains]
    if args.args:
        # En Windows shlex posix=False mantiene las barras invertidas de las rutas.
        # Las comillas se usan sólo para agrupar argumentos con espacios.
        parsed = shlex.split(args.args, posix=(os.name != "nt"))
        if os.name == "nt":
            parsed = [v[1:-1] if len(v) >= 2 and v[0] == v[-1] == '"' else v for v in parsed]
        cmd += parsed
    cmd += engine_argv  # Compatibilidad con separador --
    print("EJECUTANDO:", subprocess.list2cmdline(cmd), flush=True)
    # La salida estándar de Python usa la consola de Windows para Unicode.
    # El stderr del motor NO debe heredarse directamente: sus bytes UTF-8
    # pueden interpretarse con la página de códigos OEM/ANSI y romper emojis.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (OSError, ValueError):
                pass
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", bufsize=1)
    except OSError as exc:
        ap.error(f"No se pudo ejecutar el motor: {exc}")

    stderr_thread = threading.Thread(target=forward_stderr, args=(proc,), daemon=True)
    stderr_thread.start()
    try:
        send(proc, "uci")
        until(proc, "uciok")
        send(proc, "isready")
        until(proc, "readyok")
        send(proc, "position startpos" if args.fen == "startpos" else "position fen " + args.fen)
        go = f"go depth {args.depth} qdepth {args.qdepth} movetime {args.movetime}"
        if args.moves:
            go += " searchmoves " + " ".join(args.moves)
        send(proc, go)
        start = time.monotonic()
        while True:
            line = receive(proc)
            if line.startswith("bestmove "):
                bestmove = line.split()[1]
                break
        print(f"\nRESULTADO: bestmove={bestmove}, tiempo_pared={(time.monotonic()-start)*1000:.0f} ms")
    finally:
        if proc.poll() is None:
            try:
                send(proc, "quit")
            except RuntimeError:
                pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if proc.stdin:
            try:
                proc.stdin.close()
            except OSError:
                pass
        if proc.stdout:
            proc.stdout.close()
        stderr_thread.join(timeout=1)
        if proc.stderr:
            proc.stderr.close()


if __name__ == "__main__":
    main()
