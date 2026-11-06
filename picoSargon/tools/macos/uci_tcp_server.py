#!/usr/bin/env python3
"""Listener UCI TCP multisesión para picoSargon macOS; sólo biblioteca estándar.

Una conexión TCP equivale a un proceso UCI independiente: tablero, búsqueda y
estado no se comparten entre clientes. Logs en stderr, nunca dentro del canal TCP.
"""
import argparse
import logging
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

LOG = logging.getLogger("picoSargon-macOS")


def arguments():
    ap = argparse.ArgumentParser(description="picoSargon macOS UCI TCP listener")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=6200)
    ap.add_argument("--engine", required=True, type=Path)
    ap.add_argument("--weights", required=True, type=Path)
    ns = ap.parse_args()
    if not 1 <= ns.port <= 65535:
        ap.error("--port debe estar entre 1 y 65535")
    if not ns.engine.is_file() or not ns.weights.is_file():
        ap.error("no se encuentra ejecutable o red NNUE")
    return ns


def handle(conn, addr, session, ns):
    who = f"#{session} {addr[0]}:{addr[1]}"
    LOG.info("CONEXION %s aceptada", who)
    proc = None
    try:
        proc = subprocess.Popen(
            [str(ns.engine), "--weights", str(ns.weights)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0,
        )
        done = threading.Event()

        def engine_output():
            try:
                for data in iter(proc.stdout.readline, b""):
                    message = data.decode("utf-8", "replace").strip()
                    if message.startswith(("info ", "bestmove ", "id name", "uciok", "readyok")):
                        LOG.info("UCI %s %s", who, message)
                    conn.sendall(data)
            except (OSError, ValueError):
                pass
            finally:
                done.set()

        def engine_errors():
            try:
                for data in iter(proc.stderr.readline, b""):
                    LOG.warning("MOTOR %s %s", who, data.decode("utf-8", "replace").rstrip())
            except (OSError, ValueError):
                pass

        tout = threading.Thread(target=engine_output, daemon=True)
        terr = threading.Thread(target=engine_errors, daemon=True)
        tout.start(); terr.start()
        conn.settimeout(0.5)
        buffer = b""
        quit_requested = False
        while proc.poll() is None and not done.is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > 65536:
                LOG.error("UCI %s línea excesivamente larga", who)
                break
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                command = line.strip().decode("utf-8", "replace")
                if command.split(" ", 1)[0] in ("uci", "isready", "position", "go", "quit"):
                    LOG.info("RX %s %s", who, command[:300])
                try:
                    proc.stdin.write(line + b"\n")
                except (OSError, BrokenPipeError, ValueError):
                    quit_requested = True
                    break
                if command == "quit":
                    quit_requested = True
                    break
            if quit_requested:
                break
        if quit_requested:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
    except (OSError, ValueError) as exc:
        LOG.error("SESION %s: %s", who, exc)
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream:
                    try: stream.close()
                    except OSError: pass
        try: conn.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        conn.close()
        LOG.info("DESCONEXION %s", who)


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    ns = arguments()
    stop = threading.Event()
    def shutdown(_signum, _frame):
        stop.set()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    LOG.info("INICIO picoSargon macOS UCI/TCP")
    LOG.info("Motor: %s", ns.engine)
    LOG.info("Red NNUE: %s", ns.weights)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((ns.host, ns.port))
            listener.listen()
            listener.settimeout(0.5)
            LOG.info("ESCUCHANDO TCP %s:%d", ns.host, ns.port)
            if ns.host not in ("localhost", "127.0.0.1", "::1"):
                LOG.warning("Listener accesible desde red; limitar acceso mediante firewall")
            i = 0
            while not stop.is_set():
                try:
                    conn, addr = listener.accept()
                except socket.timeout:
                    continue
                i += 1
                threading.Thread(target=handle, args=(conn, addr, i, ns), daemon=True).start()
    except OSError as exc:
        LOG.error("No se puede abrir el listener %s:%d: %s", ns.host, ns.port, exc)
        return 1
    LOG.info("Listener detenido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
