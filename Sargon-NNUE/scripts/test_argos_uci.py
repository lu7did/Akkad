#!/usr/bin/env python3
"""Diagnóstico UCI de un brain de Akkad. v0.1.0.
Usa exactamente get/resolve_paths/to_argv del benchmark.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    ap = argparse.ArgumentParser(description="Prueba directa UCI de argos usando el mismo lanzador que benchmark")
    ap.add_argument("--id", default="argos", help="Brain (default: argos)")
    ap.add_argument("--brain", default=str(ROOT / "etc/brains/brains.json"), help="Archivo de perfiles")
    ap.add_argument("--timeout", type=float, default=120.0, help="Segundos máximos por respuesta UCI")
    ap.add_argument("--python", default=sys.executable, help="Intérprete que ejecuta el motor")
    ap.add_argument("--out", default=str(ROOT / "data/benchmark/diagnostic_argos.log"), help="Log de prueba")
    args = ap.parse_args()
    if args.timeout <= 0: ap.error("timeout debe ser positivo")
    try:
        from sargon_nnue.brains import get, to_argv
        from sargon_nnue.sargon_benchmark import resolve_paths
        brain_file = Path(args.brain).resolve()
        cfg = resolve_paths(get(brain_file, args.id), ROOT, brain_file)
        command = [args.python, "-m", "sargon_nnue.sargon_listen", "--mode", "STDIN", *to_argv(cfg)]
    except Exception as exc:
        print(f"ERROR preparando brain: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    events = queue.Queue()
    t0 = time.monotonic()
    log = out.open("w", encoding="utf-8", buffering=1)
    lock = threading.Lock()
    def record(channel, value):
        line = f"[{time.monotonic()-t0:9.3f}s] {channel} {value}"
        with lock:
            print(line, flush=True)
            log.write(line + "\n")
    record("INFO", f"brain={args.id} python={args.python} timeout={args.timeout}s")
    record("INFO", f"command={command!r}")
    record("INFO", f"network={cfg.get('network', '(no configurada)')}")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.Popen(command, cwd=str(ROOT), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0)
    except OSError as exc:
        record("ERROR", f"No se pudo iniciar: {exc}")
        log.close()
        return 2
    record("INFO", f"pid={proc.pid}")

    def drain(stream, label):
        try:
            for raw in iter(stream.readline, b""):
                msg = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                record(label, msg)
                if label == "STDOUT": events.put(msg)
        except Exception as exc:
            record("ERROR", f"lectura {label}: {exc}")
        finally:
            if label == "STDOUT": events.put(None)

    readers = [threading.Thread(target=drain, args=(proc.stdout,"STDOUT"),daemon=True),
               threading.Thread(target=drain, args=(proc.stderr,"STDERR"),daemon=True)]
    for t in readers:t.start()

    def send(cmd):
        record("STDIN ",cmd)
        if proc.poll() is not None: return False
        try:
            proc.stdin.write((cmd+"\n").encode())
            proc.stdin.flush()
            return True
        except (OSError,ValueError) as exc:
            record("ERROR", f"envío fallido: {exc}")
            return False

    def wait_for(token):
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline:
            try: line=events.get(timeout=min(0.25,max(0.001,deadline-time.monotonic())))
            except queue.Empty:
                if proc.poll() is not None:
                    record("ERROR", f"Motor terminó antes de {token}: exit={proc.returncode}")
                    return False
                continue
            if line is None:
                record("ERROR", f"EOF antes de {token}; exit={proc.poll()}")
                return False
            if line.strip()==token:
                record("OK",f"{token} recibido tras {time.monotonic()-t0:.3f}s")
                return True
        record("ERROR",f"Timeout de {token} tras {args.timeout:.1f}s")
        return False

    success=False
    try:
        success=(send("uci") and wait_for("uciok")
            and send("isready") and wait_for("readyok"))
        if success:
            record("OK", "Handshake UCI completo; sin ejecutar búsqueda")
    finally:
        send("quit")
        try: proc.stdin.close()
        except OSError: pass
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            record("WARN", "El motor no terminó con quit; terminando proceso")
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
        for t in readers: t.join(timeout=1)
        record("INFO",f"exit={proc.returncode} log={out}")
        log.close()
    return 0 if success else 1

if __name__=="__main__":
    raise SystemExit(main())
