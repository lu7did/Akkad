#!/usr/bin/env python3
"""picoSargon macOS: servidor UCI/TCP multicliente; telemetría solo a stderr."""
import argparse
import os
from datetime import datetime
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading

VERSION = '0.2.49'
PRINT_LOCK = threading.Lock()


def emit(symbol, message):
    with PRINT_LOCK:
        print(f'{datetime.now():%H:%M:%S} {symbol} {message}', file=sys.stderr, flush=True)


def arguments():
    ap = argparse.ArgumentParser(description='picoSargon macOS UCI/TCP listener')
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=6200)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--weights', type=Path, required=True)
    ap.add_argument('--cores', type=int)
    ap.add_argument('--depth', type=int)
    ap.add_argument('--qdepth', type=int)
    ap.add_argument('--timeout', type=int)
    ap.add_argument('--brains', type=Path)
    ap.add_argument('--brain', default='tinySargon')
    ns = ap.parse_args()
    if not 1 <= ns.port <= 65535:
        ap.error('--port debe estar entre 1 y 65535')
    if ns.cores is not None and not 1 <= ns.cores <= 1024:
        ap.error('--cores debe estar entre 1 y 1024')
    if ns.depth is not None and not 1 <= ns.depth <= 40: ap.error('--depth debe estar entre 1 y 40')
    if ns.qdepth is not None and not 0 <= ns.qdepth <= 32: ap.error('--qdepth debe estar entre 0 y 32')
    if ns.timeout is not None and not 1 <= ns.timeout <= 2147483647: ap.error('--timeout debe estar entre 1 y 2147483647 ms')
    if ns.brains is not None and not ns.brains.is_file(): ap.error('--brains no existe')
    if not ns.engine.is_file() or not ns.weights.is_file():
        ap.error('no se encuentra ejecutable o red NNUE')
    # Determine the build mode from the actual engine UCI interface, not
    # from an environment variable or an assumption about CMake cache.
    try:
        probe = subprocess.run(
            [str(ns.engine), '--weights', str(ns.weights)],
            input='uci\nquit\n', text=True, capture_output=True,
            timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        ap.error(f'no se pudo consultar las opciones UCI del motor: {exc}')
    if probe.returncode != 0 or 'uciok' not in probe.stdout.splitlines():
        ap.error('el ejecutable no completo correctamente el handshake UCI')
    multicore = any(line.strip().startswith('option name Cores ') for line in probe.stdout.splitlines())
    if multicore and ns.cores is None:
        ap.error('MULTICORE=ON: es obligatorio indicar --cores N (ejemplo: --cores 4)')
    if not multicore and ns.cores is not None:
        ap.error('MULTICORE=OFF: este ejecutable no admite --cores; recompilar con MULTICORE=ON')
    ns.multicore = multicore
    # The host C++ engine caps workers at physical cores; match macOS logic.
    if multicore:
        physical = None
        if sys.platform == 'darwin':
            try:
                found = subprocess.run(
                    ['sysctl', '-n', 'hw.physicalcpu'],
                    capture_output=True, text=True, timeout=3, check=True,
                )
                physical = int(found.stdout.strip())
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        if not physical or physical < 1:
            physical = os.cpu_count() or 1
        ns.effective_cores = min(ns.cores, physical)
    else:
        ns.effective_cores = 1
    return ns


def engine_args(ns):
    args = [str(ns.engine), '--weights', str(ns.weights)]
    if ns.brains is not None: args += ['--brains', str(ns.brains), '--brain', ns.brain]
    for key in ('cores','depth','qdepth','timeout'):
        value = getattr(ns, key)
        if value is not None: args += ['--' + key, str(value)]
    return args

def handle(conn, addr, ns):
    emit('✅', f'Client connected fm {addr[0]}:{addr[1]}')
    proc = None
    try:
        proc = subprocess.Popen(
            engine_args(ns),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0,
        )
        done = threading.Event()

        def engine_output():
            try:
                for data in iter(proc.stdout.readline, b''):
                    message = data.decode('utf-8', 'replace').strip()
                    if message.startswith(('info ', 'bestmove ')):
                        emit('🧠', message)
                    conn.sendall(data)
            except (OSError, ValueError):
                pass
            finally:
                done.set()

        def engine_errors():
            try:
                for data in iter(proc.stderr.readline, b''):
                    message = data.decode('utf-8', 'replace').rstrip()
                    # El motor informa su propio arranque por stderr; el listener
                    # ya lo presentó una vez con el encabezado solicitado.
                    if message.startswith('[picoSargon ') and 'macOS UCI/stdin iniciado' in message:
                        continue
                    if message.startswith('[') and ' 🧮 core[' in message:
                        # The engine owns per-core timestamps and formatting.
                        # Keep each record intact and do not prefix it with a warning.
                        with PRINT_LOCK:
                            print(message, file=sys.stderr, flush=True)
                    elif message:
                        emit('⚠️', f'Motor: {message}')
            except (OSError, ValueError):
                pass

        threading.Thread(target=engine_output, daemon=True).start()
        threading.Thread(target=engine_errors, daemon=True).start()
        conn.settimeout(0.5)
        buffer = b''
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
                emit('⚠️', 'UCI: comando demasiado largo')
                break
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                command = line.decode('utf-8', 'replace').strip()
                verb = command.split(' ', 1)[0]
                if verb in ('position', 'go'):
                    emit('➡️', f'UCI {command}')
                try:
                    proc.stdin.write(line + b'\n')
                except (OSError, BrokenPipeError, ValueError):
                    quit_requested = True
                    break
                if command == 'quit':
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
        emit('❌', f'Client error {addr[0]}:{addr[1]}: {exc}')
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
                    try:
                        stream.close()
                    except OSError:
                        pass
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()
        emit('❌', 'Client disconnected')


def main():
    ns = arguments()
    stop = threading.Event()

    def shutdown(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    emit('💻', f'picoSargon macOS UCI/TCP v{VERSION}')
    emit('⚙️', f'Motor: {ns.engine}')
    emit('⚙️', f'NNUE:  {ns.weights}')
    # Startup configuration, not the count of root moves available per position.
    with PRINT_LOCK:
        print(f'[{datetime.now():%H:%M:%S}] ⚙️ MULTICORE={ns.multicore} CORE={ns.effective_cores}', file=sys.stderr, flush=True)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((ns.host, ns.port))
            listener.listen()
            listener.settimeout(0.5)
            emit('🌐', f'Listener started TCP {ns.host}:{ns.port}')
            while not stop.is_set():
                try:
                    conn, addr = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if stop.is_set():
                        break
                    raise
                threading.Thread(target=handle, args=(conn, addr, ns), daemon=True).start()
    except OSError as exc:
        emit('❌', f'No se puede abrir el listener {ns.host}:{ns.port}: {exc}')
        return 1
    finally:
        emit('🌐', 'Listener detenido')
    return 0


if __name__ == '__main__':
    sys.exit(main())
