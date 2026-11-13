"""Non-destructive SQLite database path diagnostic for picoAlpha Genesis."""
import argparse
import os
import sqlite3
import sys


def verify(path, min_games=0):
    path = os.path.abspath(path)
    exists = os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0
    print(f'🗄️ DB input={path} exists={exists} bytes={size}', flush=True)
    if not exists:
        raise ValueError('Input database does not exist at the reported path')
    # mode=ro prevents sqlite3.connect from creating a new empty database on typos.
    uri = 'file:' + __import__('pathlib').Path(path).as_posix() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        print('🗄️ DB tables=' + ','.join(sorted(tables)), flush=True)
        if not {'games', 'positions'} <= tables:
            raise ValueError(f"Schema mismatch: missing {sorted({'games', 'positions'}-tables)}")
        games = db.execute('SELECT count(*) FROM games').fetchone()[0]
        positions = db.execute('SELECT count(*) FROM positions').fetchone()[0]
        print(f'🗄️ DB games={games} positions={positions}', flush=True)
        if games < min_games or (min_games > 0 and positions < 1):
            raise ValueError(f'Database contains insufficient training data: games={games}, positions={positions}')
    return True


def main():
    parser = argparse.ArgumentParser(description='Print absolute path and verify existing picoAlpha SQLite .pb database (read only)')
    parser.add_argument('--in', dest='source', required=True)
    parser.add_argument('--min-games', type=int, default=0)
    args = parser.parse_args()
    try:
        verify(args.source, args.min_games)
    except (sqlite3.Error, ValueError, OSError) as exc:
        print(f'❌ DB ERROR: {exc}', file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
