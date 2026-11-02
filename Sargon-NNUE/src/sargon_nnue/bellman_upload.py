"""Accumulating PGN importer for Bellman-Restricted.

Standalone SQLite .pb store. Only original game records are stored; no NNUE features.
Designed to be directly readable by Bellman-prepare's embedded-PGN loader.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import logging
import shutil
import re
import sqlite3
import sys
import time
from pathlib import Path

try:
    import chess.pgn
except ImportError as exc:
    raise SystemExit('Falta python-chess. Instalar con: python -m pip install python-chess') from exc

FORMAT = 'SARGON-PB-SQLITE-1'
UPLOAD_FORMAT = 'BELLMAN-PGN-STORE-1'
RESULTS = {'0-1': 0, '1/2-1/2': 1, '1-0': 2}

# python-chess registra SAN inválido por logging antes de agregarlo a game.errors.
# La importación lo trata como partida omitida, sin volcar mensajes al terminal.
logging.getLogger('chess.pgn').addHandler(logging.NullHandler())
logging.getLogger('chess.pgn').propagate = False


def resolve_files(expression: str) -> list[Path]:
    """Glob by default; prefix re: to select full-path regular expression."""
    expression = expression.strip().strip('"')
    if expression.lower().startswith('re:'):
        pattern = expression[3:].replace('\\\\', '/')
        rx = re.compile(pattern, re.IGNORECASE)
        # Determine a stable directory prefix before the first regex operator.
        match = re.search(r'(?<!\\)[\[\]()*+?{|^$]', pattern)
        literal = pattern[:match.start()] if match else pattern
        parent = Path(literal.rsplit('/', 1)[0] or '.')
        while not parent.is_dir() and parent != parent.parent:
            parent = parent.parent
        root = parent if parent.is_dir() else Path('.')
        candidates = (p for p in root.rglob('*') if p.is_file() and p.suffix.lower() == '.pgn')
        found = [p.resolve() for p in candidates if rx.search(p.resolve().as_posix())]
    else:
        found = [Path(p).resolve() for p in glob.glob(expression, recursive=True)
                 if Path(p).is_file() and Path(p).suffix.lower() == '.pgn']
    return sorted(set(found), key=lambda p: str(p).lower())


_progress_width = 0


def _one_line(message: str) -> None:
    """Reescribe una única línea, sin desbordar el ancho disponible del terminal."""
    global _progress_width
    columns = shutil.get_terminal_size(fallback=(120, 24)).columns
    max_width = max(1, columns - 1)  # Evita el wrap automático en consola.
    displayed = message if len(message) <= max_width else message[:max_width - 1] + '…'
    # Borrar restos de una actualización previa más larga, sin generar nueva línea.
    print('\r' + displayed + ' ' * max(0, min(max_width, _progress_width) - len(displayed)),
          end='', flush=True)
    _progress_width = len(displayed)


def _end_line() -> None:
    global _progress_width
    if _progress_width:
        print()
        _progress_width = 0


def count_progress(index: int, total: int, games: int, name: str) -> None:
    ratio = 100 * index / total if total else 100
    _one_line(f'🔎 Archivos {index:,}/{total:,} ({ratio:5.1f}%) · '
              f'{games:,} partidas detectadas · {name}')


def import_progress(file_index: int, total_files: int, done_games: int,
                    total_games: int, name: str) -> None:
    file_percent = 100 * file_index / total_files if total_files else 100
    game_percent = 100 * done_games / total_games if total_games else 100
    # Barra breve para que el nombre del PGN quepa en la misma línea.
    bar_width = 24
    filled = min(bar_width, int(bar_width * game_percent / 100))
    bar = '█' * filled + '░' * (bar_width - filled)
    _one_line(f'📥 {file_index:,}/{total_files:,} ({file_percent:5.1f}%) '
              f'partidas {done_games:,}/{total_games:,} [{bar}] '
              f'{game_percent:5.1f}% · {name}')


def iter_games(path: Path):
    """Stream PGN games; reserialize parsed contents without materializing the file."""
    with path.open('r', encoding='utf-8-sig', errors='replace') as source:
        game_index = 0
        while True:
            game = chess.pgn.read_game(source)
            if game is None:
                break
            game_index += 1
            yield game_index, game, game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=True))


def game_identity(game, result: str) -> tuple[str, int]:
    # Game identity is independent of PGN whitespace, path and import order.
    # Headers distinguish distinct games with identical move sequences.
    headers = '\n'.join(f'{k}={v}' for k, v in sorted(game.headers.items())
                        if k not in ('PlyCount',))
    moves = ' '.join(move.uci() for move in game.mainline_moves())
    source = f'{headers}\nRESULT={result}\nMOVES={moves}'.encode('utf-8')
    return hashlib.sha256(source).hexdigest(), (len(moves.split()) if moves else 0)


def open_db(path: Path) -> sqlite3.Connection:
    if path.exists() and path.stat().st_size:
        with path.open('rb') as fh:
            if fh.read(16) != b'SQLite format 3\x00':
                raise ValueError(f'El destino existe y no es SQLite: {path}')
    db = sqlite3.connect(path, timeout=60)
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=60000')
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        present = db.execute("SELECT value FROM meta WHERE key='format'").fetchone()
        if present is not None and present[0] != FORMAT:
            raise ValueError(f'Formato incompatible: {present[0]}')
        db.execute('CREATE TABLE IF NOT EXISTS games ('
                   'id INTEGER PRIMARY KEY, source TEXT NOT NULL, source_index INTEGER NOT NULL, '
                   'result INTEGER NOT NULL CHECK(result IN (0,1,2)), npositions INTEGER NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS pgn_games ('
                   'game_id INTEGER PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE, pgn TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS bellman_game_identity ('
                   'game_hash TEXT PRIMARY KEY, game_id INTEGER UNIQUE NOT NULL '
                   'REFERENCES games(id) ON DELETE CASCADE)')
        db.execute('INSERT OR IGNORE INTO meta(key,value) VALUES (?,?)', ('format', FORMAT))
        db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)', ('bellman_upload_format', UPLOAD_FORMAT))
        db.commit()
    except BaseException:
        db.rollback()
        db.close()
        raise
    return db


def run(args: argparse.Namespace) -> int:
    files = resolve_files(args.path)
    if not files:
        print(f'❌ No se encontraron archivos .pgn para: {args.path}', file=sys.stderr)
        return 2
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f'📁 Archivos PGN encontrados: {len(files):,}')
    print('🔎 Contando partidas para calcular porcentaje global...')
    per_file = []
    total_games = 0
    for i, file in enumerate(files, 1):
        count = sum(1 for _ in iter_games(file))
        per_file.append(count)
        total_games += count
        count_progress(i, len(files), total_games, file.name)
    _end_line()
    print(f'📚 Partidas detectadas: {total_games:,} · destino: {out}')
    db = open_db(out)
    imported = duplicate = skipped = complete = seen_moves = 0
    start = time.monotonic()
    try:
        # Existing DBs from older imports may lack hashes: backfill identity
        # from embedded PGNs to keep repeat uploads idempotent.
        previous = db.execute('SELECT count(*) FROM games').fetchone()[0]
        existing_hashes = db.execute('SELECT count(*) FROM bellman_game_identity').fetchone()[0]
        if previous != existing_hashes:
            print(f'🔄 Indexando identidades históricas: {existing_hashes:,}/{previous:,}')
            for gid, raw in db.execute('SELECT game_id,pgn FROM pgn_games'):
                old_game = chess.pgn.read_game(io.StringIO(raw))
                if old_game and not old_game.errors:
                    result = old_game.headers.get('Result', '*')
                    if result in RESULTS:
                        key, _ = game_identity(old_game, result)
                        db.execute('INSERT OR IGNORE INTO bellman_game_identity(game_hash,game_id) VALUES (?,?)', (key,gid))
            db.commit()
        for fi, (file, n_games) in enumerate(zip(files, per_file), 1):
            file_imported = file_duplicate = file_skipped = 0
            try:
                db.execute('BEGIN IMMEDIATE')
                for local_index, game, pgn_text in iter_games(file):
                    complete += 1
                    result = game.headers.get('Result', '*')
                    if result not in RESULTS or game.errors:
                        skipped += 1; file_skipped += 1
                    else:
                        key, n_moves = game_identity(game, result)
                        if db.execute('SELECT 1 FROM bellman_game_identity WHERE game_hash=?', (key,)).fetchone():
                            duplicate += 1; file_duplicate += 1
                        else:
                            cur = db.execute('INSERT INTO games(source,source_index,result,npositions) VALUES (?,?,?,?)',
                                             (str(file),local_index,RESULTS[result],n_moves))
                            gid = cur.lastrowid
                            db.execute('INSERT INTO pgn_games(game_id,pgn) VALUES (?,?)', (gid,pgn_text))
                            db.execute('INSERT INTO bellman_game_identity(game_hash,game_id) VALUES (?,?)', (key,gid))
                            imported += 1; file_imported += 1
                            seen_moves += n_moves
                    if complete == 1 or complete % max(1, total_games // 300) == 0 or complete == total_games:
                        import_progress(fi, len(files), complete, total_games, file.name)
                db.commit()
            except BaseException:
                db.rollback()
                raise
            import_progress(fi, len(files), complete, total_games, file.name)
        _end_line()
        total_db, moves_db = db.execute('SELECT count(*),coalesce(sum(npositions),0) FROM games').fetchone()
        embedded = db.execute('SELECT count(*) FROM pgn_games').fetchone()[0]
        print(f'✅ Nuevas: {imported:,} · repetidas: {duplicate:,} · omitidas: {skipped:,}')
        print(f'📚 Base total: {total_db:,} partidas · {moves_db:,} movimientos · PGN internos: {embedded:,}')
        print(f'💾 {out.stat().st_size:,} bytes · {time.monotonic()-start:.1f} s')
        return 0
    finally:
        _end_line()
        db.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Carga acumulativa de partidas PGN a base .pb para BellmanR')
    p.add_argument('--path', required=True, help='Patrón glob (ej. data/**/*.pgn) o re:expresión_regular')
    p.add_argument('--out', required=True, help='Base SQLite .pb de destino; se crea o amplía')
    args = p.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(f'❌ bellman_upload: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
