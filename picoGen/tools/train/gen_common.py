"""Shared contracts for picoGenus genetic training v0.1.1 (stdlib + NumPy)."""
import math
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

TABLES = {'games', 'positions'}
COLS = ('ply', 'fen', 'played_uci', 'teacher_uci', 'teacher_cp', 'teacher_mate',
        'teacher_value', 'teacher_depth', 'teacher_at')
CREATE_SQL = '''
PRAGMA foreign_keys=ON;
CREATE TABLE games (id INTEGER PRIMARY KEY, source_file TEXT NOT NULL,
 source_ordinal INTEGER NOT NULL, headers_json TEXT NOT NULL, result TEXT NOT NULL,
 start_fen TEXT NOT NULL, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_file,source_ordinal));
CREATE TABLE positions (id INTEGER PRIMARY KEY,
 game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
 ply INTEGER NOT NULL, fen TEXT NOT NULL, played_uci TEXT NOT NULL,
 teacher_uci TEXT, teacher_cp INTEGER, teacher_mate INTEGER,
 teacher_value REAL, teacher_depth INTEGER, teacher_at TEXT, UNIQUE(game_id,ply));
CREATE INDEX idx_positions_game ON positions(game_id,ply);
CREATE INDEX idx_positions_teacher ON positions(teacher_value);
'''


def open_source(path):
    full = Path(path).expanduser().resolve()
    if not full.is_file():
        raise ValueError(f'Base de entrada inexistente: {full}')
    db = sqlite3.connect(full.as_uri() + '?mode=ro', uri=True)
    found = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not TABLES <= found:
        db.close()
        raise ValueError(f'Esquema incorrecto en {full}: faltan {sorted(TABLES - found)}')
    print(f'🗄️ DB input={full} bytes={full.stat().st_size} '
          f'games={db.execute("SELECT COUNT(*) FROM games").fetchone()[0]} '
          f'positions={db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]}', flush=True)
    return db


def check_output(src, dst):
    if Path(src).expanduser().resolve() == Path(dst).expanduser().resolve():
        raise ValueError('--in y --out deben ser diferentes')


def require_chess():
    try:
        import chess
        import chess.engine
        return chess
    except ImportError as ex:
        raise RuntimeError('Falta python-chess: instalar con pip install -r requirements.txt') from ex


class Progress:
    """Single physical console line; fixed fields; no carriage returns in redirected logs."""
    def __init__(self, label, total):
        self.label = label[:10]
        self.total = max(0, int(total))
        self.width = max(1, len(str(self.total)))
        self.tty = bool(getattr(sys.stdout, 'isatty', lambda: False)())
        self.last = -1

    def update(self, done, force=False):
        done = max(0, min(int(done), self.total))
        if not self.tty and done < self.total and not force:
            return
        # Leave 2 spare columns to avoid PowerShell auto-wrap.
        available = shutil.get_terminal_size((80, 24)).columns
        structural = len(self.label) + 2 + 1 + 1 + 2 + 7 + 1 + self.width * 2 + 1
        length = max(4, min(24, available - structural - 3))
        fraction = 1 if not self.total else done / self.total
        used = round(length * fraction)
        line = (f'{self.label:<10} [{"█" * used}{"░" * (length - used)}] '
                f'{100*fraction:6.2f}% {done:>{self.width}d}/{self.total:>{self.width}d}')
        if self.tty:
            # Avoid printing the same intermediate percentage unnecessarily.
            if not force and done == self.last:
                return
            sys.stdout.write('\r' + line + '\x1b[K' + ('\n' if done >= self.total else ''))
        elif done >= self.total or force:
            sys.stdout.write(line + '\n')
        sys.stdout.flush()
        self.last = done


def target_cp(row, turn):
    """Teacher label from side-to-move POV -> white POV in centipawns."""
    cp, mate, value = row
    if mate is not None:
        cp = 2000 if mate > 0 else -2000
    elif cp is None and value is not None:
        v = max(-0.99999, min(0.99999, float(value)))
        cp = 400 * math.atanh(v)
    if cp is None:
        return None
    return float(np.clip(cp if turn else -cp, -2000, 2000))


def select_rows(db, *, require_move=False):
    query = ('SELECT id,fen,teacher_uci,teacher_cp,teacher_mate,teacher_value '
             'FROM positions WHERE (teacher_cp IS NOT NULL OR teacher_mate IS NOT NULL '
             'OR teacher_value IS NOT NULL)')
    if require_move:
        query += ' AND teacher_uci IS NOT NULL'
    return db.execute(query + ' ORDER BY id')


def load_labeled(db, *, seed=42, max_rows=0, require_move=False):
    """Reservoir sample for optional cap; zero means all labeled rows."""
    import random
    rand = random.Random(seed)
    out = []
    seen = 0
    for row in select_rows(db, require_move=require_move):
        seen += 1
        if max_rows == 0 or len(out) < max_rows:
            out.append(row)
        else:
            replacement = rand.randrange(seen)
            if replacement < max_rows:
                out[replacement] = row
    print(f'🧬 labeled={seen} selected={len(out)} seed={seed} cap={max_rows or "all"}', flush=True)
    if not out:
        raise ValueError('La base no contiene posiciones etiquetadas por Stockfish')
    return out


def atomic_path(target, suffix):
    target = Path(target).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + target.stem + '.', suffix=suffix, dir=target.parent)
    os.close(fd)
    return target, Path(name)


def validate_board(fen, chess):
    try:
        b = chess.Board(fen)
        if not b.is_valid():
            return None
        return b
    except ValueError:
        return None
