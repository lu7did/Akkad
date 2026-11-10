#!/usr/bin/env python3
"""Prueba end-to-end de brains Nurse mediante un listener UCI/TCP local.

Ejecutar desde el directorio nurse, con el paquete instalado (pip install -e .):
    python nurse_dryrun.py --brains etc/brains/brains.json --id fishy picoSargon
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import threading
import time
from pathlib import Path

import chess

# Permitir ejecutar el archivo desde su ubicación sin instalación editable.
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from nurse import __version__
from nurse.benchmark_bratko_kopec import choose_positions
from nurse.config import read_brains, read_brain
from nurse.listen import serve_client


def trace(direction, line):
    print(f'      {direction} {line}', flush=True)


def take_until(inp, expected, timeout, status):
    """Consume UCI lines until a handshake marker; fail on EOF/error."""
    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(f'timeout esperando {expected}')
        line = inp.readline()
        if not line:
            raise ConnectionError(f'EOF antes de {expected}')
        line = line.rstrip('\r\n')
        trace('⬅️', line)
        if line.startswith('info string nurse error '):
            raise RuntimeError(line[len('info string nurse error '):])
        if line.startswith('info string nurse_external_provenance '):
            try:
                status['remote_name'] = json.loads(line.split(' ', 3)[3]).get('uci_name')
            except (ValueError, IndexError, TypeError) as exc:
                raise RuntimeError('procedencia UCI externa inválida') from exc
        if line.startswith('id name '):
            status['frontend_name'] = line[8:]
        if line == expected:
            return


def send(out, line):
    trace('➡️', line)
    out.write(line + '\n')
    out.flush()


def solve_one(port, ident, cfg, fen):
    """Actúa como cliente UCI de un listener Nurse TCP, nunca del backend directamente."""
    status = {'remote_name': None, 'frontend_name': None}
    t0 = time.monotonic()
    outcome = {'id': ident, 'type': cfg['_type'], 'ok': False, 'ms': 0.,
               'name': ident, 'bestmove': '—', 'nodes': None, 'depth': None,
               'engine_ms': None, 'search_ms': None, 'error': None}
    limit = (cfg['tmax'] + cfg['timeout']) / 1000
    search_started = None
    try:
        # The TCP listener is truly local. The remote address is exclusively
        # selected by Nurse from the validated brains.json profile.
        with socket.create_connection(('127.0.0.1', port), timeout=cfg['timeout']/1000) as sock:
            sock.settimeout(cfg['timeout']/1000)
            with sock.makefile('r', encoding='utf-8', errors='replace', newline='\n') as inp, \
                 sock.makefile('w', encoding='utf-8', newline='\n') as out:
                send(out, 'uci')
                take_until(inp, 'uciok', cfg['timeout']/1000, status)
                send(out, 'isready')
                take_until(inp, 'readyok', cfg['timeout']/1000, status)
                send(out, 'ucinewgame')
                send(out, 'position fen ' + fen)
                search_started = time.monotonic()
                send(out, f'go movetime {cfg["tmax"]}')
                sock.settimeout(limit + 2)
                deadline = time.monotonic() + limit + 2
                board = chess.Board(fen)
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('no se recibió bestmove dentro del presupuesto')
                    raw = inp.readline()
                    if not raw:
                        raise ConnectionError('EOF durante la búsqueda')
                    line = raw.rstrip('\r\n')
                    trace('⬅️', line)
                    if line.startswith('info string nurse error '):
                        raise RuntimeError(line[len('info string nurse error '):])
                    if line.startswith('info '):
                        for field in ('nodes', 'depth', 'time'):
                            m = re.search(r'(?<!\S)' + field + r'\s+(\d+)(?=\s|$)', line)
                            if m:
                                outcome['engine_ms' if field == 'time' else field] = int(m.group(1))
                    if line.startswith('bestmove '):
                        move = line.split()[1] if len(line.split()) > 1 else ''
                        if move in ('', '0000', '(none)'):
                            raise RuntimeError(f'bestmove inválido: {move or "vacío"}')
                        try:
                            legal = chess.Move.from_uci(move) in board.legal_moves
                        except ValueError:
                            legal = False
                        if not legal:
                            raise RuntimeError(f'bestmove ilegal: {move}')
                        outcome['bestmove'] = move
                        outcome['search_ms'] = (time.monotonic() - search_started) * 1000
                        outcome['ok'] = True
                        break
                send(out, 'quit')
    except (OSError, ConnectionError, TimeoutError, RuntimeError, ValueError) as exc:
        outcome['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        finished = time.monotonic()
        outcome['ms'] = (finished - t0) * 1000
        if search_started is not None and outcome['search_ms'] is None:
            outcome['search_ms'] = (finished - search_started) * 1000
        if cfg['_type'] == 'external':
            outcome['name'] = status['remote_name'] or '(nombre UCI no recibido)'
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Dryrun UCI: una posición aleatoria Bratko–Kopec para cada brain, mediante TCP localhost:6200')
    parser.add_argument('--brains', required=True, help='archivo brains.json')
    parser.add_argument('--id', nargs='+', required=True, metavar='BRAIN', help='uno o más IDs de brains')
    parser.add_argument('--port', type=int, default=6200, help='puerto del wrapper TCP local (default 6200)')
    parser.add_argument('--seed', type=int, help='semilla opcional para reproducir la posición aleatoria')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('--port debe estar entre 1 y 65535')
    source = Path(args.brains).expanduser().resolve()
    try:
        # Validate the ENTIRE file before opening the listener. In particular,
        # json duplicate keys must never be silently overwritten.
        read_brains(source)
        if len(args.id) != len(set(args.id)):
            raise ValueError('--id contiene un brain repetido')
        configs = {ident: read_brain(source, ident) for ident in args.id}
        bk_id, fen = choose_positions(1, args.seed)[0]
        chess.Board(fen)  # Explicitly validate dataset entry before connecting.
    except (OSError, ValueError, KeyError) as exc:
        print(f'❌ Configuración: {exc}', file=sys.stderr)
        return 2

    print(f'🧠 NURSE DRYRUN v{__version__} | brains={source}', flush=True)
    print(f'♟️ Bratko–Kopec #{bk_id} | turno={"blancas" if chess.Board(fen).turn else "negras"}', flush=True)
    print(f'   FEN: {fen}', flush=True)
    print(f'🌐 Wrapper UCI/TCP localhost:{args.port}', flush=True)

    # Bind exactly once; each successive connection gets its own Nurse
    # instance with the specified brain ID. The wrapper is not a fake UCI
    # engine: the selected backend is contacted by Nurse itself.
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', args.port))
        listener.listen(1)
    except OSError as exc:
        print(f'❌ No se pudo abrir localhost:{args.port}: {exc}', file=sys.stderr)
        try: listener.close()
        except (OSError, UnboundLocalError): pass
        return 2

    results = []
    try:
        for i, ident in enumerate(args.id, 1):
            cfg = configs[ident]
            print(f'\n[{i}/{len(args.id)}] {ident} ({cfg["_type"]})', flush=True)
            done = threading.Event()
            def accept_once():
                try:
                    client, address = listener.accept()
                    serve_client(client, address, str(source), ident)
                except OSError as exc:
                    print(f'❌ Error wrapper {ident}: {exc}', file=sys.stderr)
                finally:
                    done.set()
            thread = threading.Thread(target=accept_once, daemon=True)
            thread.start()
            result = solve_one(args.port, ident, cfg, fen)
            done.wait(timeout=5)
            results.append(result)
            symbol = '✅' if result['ok'] else '❌'
            stats = (f"move={result['bestmove']} nodes={result['nodes'] or 'n/d'} "
                     f"depth={result['depth'] if result['depth'] is not None else 'n/d'} "
                     f"engine_ms={result['engine_ms'] if result['engine_ms'] is not None else 'n/d'}")
            time_desc = (f"búsqueda={result['search_ms']:.1f} ms"
                         if result['search_ms'] is not None else 'búsqueda=n/d')
            print(f"   {symbol} {result['name']} | {time_desc} total={result['ms']:.1f} ms | {stats}", flush=True)
            if result['error']:
                print(f"   ❌ {result['error']}", flush=True)
    finally:
        listener.close()

    print('\n🏁 RESUMEN — tiempo de búsqueda (o total si no comenzó), orden ascendente', flush=True)
    for rank, r in enumerate(sorted(results, key=lambda x: x['search_ms'] if x['search_ms'] is not None else x['ms']), 1):
        search_text = f"{r['search_ms']:.1f}" if r['search_ms'] is not None else 'n/d'
        print(f"   {rank:2}. {'✅' if r['ok'] else '❌'} {r['name']} "
              f"[id={r['id']}, {r['type']}] "
              f"búsqueda={search_text} ms total={r['ms']:.1f} ms "
              f"move={r['bestmove']}" + (f" error={r['error']}" if r['error'] else ''), flush=True)
    return 0 if all(r['ok'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
