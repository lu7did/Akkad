"""Read-only investigation of repeated Stockfish crashes in picoAlpha teacher.

No schema changes, UPDATEs, DELETEs, or quarantine modifications.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shlex
import sqlite3
import sys
import time

DEFAULT_IDS = (3773336, 3773337, 3773338, 3773339, 3773340)
START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'


def read_rows(path, ids):
    path = Path(path).expanduser().resolve(strict=True)
    # mode=ro is mandatory: a typo never creates a fresh SQLite file.
    uri = path.as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True, timeout=15) as db:
        rows = []
        for position_id in ids:
            row = db.execute('''SELECT id, game_id, ply, fen,
                               teacher_cp, teacher_mate, teacher_at
                               FROM positions WHERE id=?''', (position_id,)).fetchone()
            if row is None:
                rows.append({'id': position_id, 'missing': True})
            else:
                rows.append(dict(zip(('id', 'game_id', 'ply', 'fen',
                                      'teacher_cp', 'teacher_mate', 'teacher_at'), row)))
    return rows


def probe(chess, command, fen, depth, nodes, timeout):
    item = {'depth': depth, 'nodes': nodes}
    engine = None
    started = time.monotonic()
    try:
        board = chess.Board(fen)
        item.update({'fen_valid': bool(board.is_valid()),
                     'legal_moves': board.legal_moves.count(),
                     'game_over': board.is_game_over(claim_draw=True)})
        if not item['fen_valid']:
            item['status'] = 'INVALID_FEN'
            return item
        engine = chess.engine.SimpleEngine.popen_uci(command, timeout=timeout)
        info = engine.analyse(board, chess.engine.Limit(depth=depth, nodes=nodes))
        score = info.get('score')
        if score is None:
            item['status'] = 'NO_SCORE'
        else:
            item['status'] = 'OK'
            item['score'] = str(score.pov(chess.WHITE))
        pv = info.get('pv') or []
        item['pv_first'] = pv[0].uci() if pv else None
    except Exception as exc:
        item['status'] = 'ENGINE_ERROR'
        item['error_type'] = type(exc).__name__
        item['error'] = str(exc)
    finally:
        item['elapsed_seconds'] = round(time.monotonic() - started, 3)
        if engine is not None:
            try:
                engine.quit()
            except Exception:
                pass
    return item


def run(args):
    try:
        import chess
        import chess.engine
    except ImportError as exc:
        raise SystemExit('python-chess no instalado en este interprete: pip install python-chess') from exc
    if args.nodes is not None and args.nodes <= 0:
        raise SystemExit('--nodes debe ser positivo')
    command = [str(Path(args.engine).expanduser())] + shlex.split(args.args, posix=(os.name != 'nt'))
    if not Path(command[0]).is_file():
        raise SystemExit('Ejecutable Stockfish no encontrado: ' + command[0])
    rows = read_rows(args.source, args.ids)
    output = {'database': str(Path(args.source).resolve()), 'engine': command,
              'rows': rows, 'tests': []}
    plans = [('control_start_depth1', START_FEN, 1, None),
             ('control_start_requested', START_FEN, args.depth, args.nodes)]
    for row in rows:
        if 'fen' in row:
            plans.append((f"position_{row['id']}_depth1", row['fen'], 1, None))
            plans.append((f"position_{row['id']}_requested", row['fen'], args.depth, args.nodes))
    print(f"DIAG source={output['database']} engine={command!r} depth={args.depth} nodes={args.nodes}", flush=True)
    for name, fen, depth, nodes in plans:
        item = probe(chess, command, fen, depth, nodes, args.timeout)
        item.update({'name': name, 'fen': fen})
        output['tests'].append(item)
        status = item['status']
        extra = item.get('error', item.get('score', ''))
        print(f'{name}: {status}  time={item["elapsed_seconds"]:.2f}s  {extra}', flush=True)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print('Report:', target.resolve(), flush=True)
    return 2 if any(t['status'] != 'OK' for t in output['tests']) else 0


def main():
    ap = argparse.ArgumentParser(description='Diagnosticar Stockfish sin modificar sample_history.pb')
    ap.add_argument('--in', dest='source', required=True, help='Base .pb SQLite de picoAlpha')
    ap.add_argument('--engine', required=True, help='Ruta absoluta al ejecutable Stockfish')
    ap.add_argument('--args', default='', help='Argumentos adicionales del ejecutable')
    ap.add_argument('--ids', nargs='+', type=int, default=list(DEFAULT_IDS))
    ap.add_argument('--depth', type=int, default=10)
    ap.add_argument('--nodes', type=int, default=None)
    ap.add_argument('--timeout', type=float, default=30.0)
    ap.add_argument('--out', default='', help='Informe JSON opcional')
    args = ap.parse_args()
    if args.depth <= 0 or args.timeout <= 0:
        ap.error('--depth y --timeout deben ser positivos')
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
