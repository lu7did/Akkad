#!/usr/bin/env python3
"""picoSargon macOS: servidor UCI/TCP multicliente; telemetría solo a stderr."""
import argparse
from datetime import datetime
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading

VERSION = '0.2.38'
PRINT_LOCK = threading.Lock()


def emit(symbol, message):
    with PRINT_LOCK:
        print(f'{datetime.now():%H:%M:%S} {symbol} {message}', file=sys.stderr, flush=True)


def arguments():
    ap = argparse.ArgumentParser(description='picoSargon macOS UCI/TCP listener')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=6200)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--weights', type=Path, required=True)
    ns = ap.parse_args()
    if not 1 <= ns.port <= 65535:
        ap.error('--port debe estar entre 1 y 65535')
    if not ns.engine.is_file() or not ns.weights.is_file():
        ap.error('no se encuentra ejecutable o red NNUE')
    return ns


def handle(conn, addr, ns):
    emit('✅', f'Client connected fm {addr[0]}:{addr[1]}')
    proc = None
    try:
        proc = subprocess.Popen(
            [str(ns.engine), '--weights', str(ns.weights)],
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
                    if message:
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
