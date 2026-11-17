#!/usr/bin/env python3
# picoAlpha mixer v0.1.21: merge existing Stockfish labels by exact FEN.
"""Create a fresh teacher-ready SQLite .pb database.

All games and positions come from --in.  Only teacher_* fields are imported
from --mix, matched by EXACT FEN.  Missing/incomplete mix labels produce NULL
teacher fields (even if --in was labeled).  No Stockfish calls are made.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import math
import os
import sqlite3
import sys
import time
from pathlib import Path

try:
    from common import schema
except ImportError:
    # The standard picoAlpha layout runs this program from tools/train.
    raise SystemExit('Missing picoAlpha/tools/train/common.py')

VERSION = '0.1.21'
FIELDS = ('teacher_uci', 'teacher_cp', 'teacher_mate', 'teacher_value',
          'teacher_depth', 'teacher_at')
GAME_FIELDS = ('id', 'source_file', 'source_ordinal', 'headers_json',
               'result', 'start_fen', 'imported_at')
POSITION_FIELDS = ('id', 'game_id', 'ply', 'fen', 'played_uci')


def fmt_time(seconds):
    if seconds is None or not math.isfinite(seconds):
        return '------:--:--'
    n = max(0, int(seconds))
    return f'{n // 3600:06d}:{n // 60 % 60:02d}:{n % 60:02d}'


class _WindowsConsole:
    """Write progress directly to CONOUT$, bypassing redirected stdout/CR filters.

    Win32 cursor positioning works in Windows PowerShell 5.1 as well as newer
    terminals; ANSI escape support and carriage-return forwarding are not needed.
    """
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.handle = None
        self._owned = False
        self._coord = wintypes._COORD if hasattr(wintypes, '_COORD') else None

        class COORD(ctypes.Structure):
            _fields_ = [('X', wintypes.SHORT), ('Y', wintypes.SHORT)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [('Left', wintypes.SHORT), ('Top', wintypes.SHORT),
                        ('Right', wintypes.SHORT), ('Bottom', wintypes.SHORT)]

        class CSBI(ctypes.Structure):
            _fields_ = [('dwSize', COORD), ('dwCursorPosition', COORD),
                        ('wAttributes', wintypes.WORD), ('srWindow', SMALL_RECT),
                        ('dwMaximumWindowSize', COORD)]

        self.COORD = COORD
        self.CSBI = CSBI
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                            wintypes.DWORD, wintypes.LPVOID,
                                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.GetConsoleScreenBufferInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(CSBI)]
        self.kernel.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
        self.kernel.SetConsoleCursorPosition.argtypes = [wintypes.HANDLE, COORD]
        self.kernel.SetConsoleCursorPosition.restype = wintypes.BOOL
        self.kernel.WriteConsoleW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR,
                                              wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                              wintypes.LPVOID]
        self.kernel.WriteConsoleW.restype = wintypes.BOOL
        self.kernel.FillConsoleOutputCharacterW.argtypes = [wintypes.HANDLE,
             wintypes.WCHAR, wintypes.DWORD, COORD, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.FillConsoleOutputCharacterW.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL

        # CONOUT$ remains connected to the real Windows console even when
        # python stdout is piped through a PowerShell wrapper.
        handle = self.kernel.CreateFileW('CONOUT$', 0xC0000000, 3, None, 3, 0, None)
        if handle in (None, wintypes.HANDLE(-1).value):
            raise OSError('Windows console not available')
        self.handle = handle
        self._owned = True
        if self.info() is None:
            self.close()
            raise OSError('Windows console screen buffer unavailable')

    def info(self):
        info = self.CSBI()
        if not self.kernel.GetConsoleScreenBufferInfo(self.handle, self.ctypes.byref(info)):
            return None
        return info

    def width(self):
        info = self.info()
        if info is None:
            return 80
        # Avoid wrapping at the visible right margin, even if buffer is wider.
        return max(30, info.srWindow.Right - info.srWindow.Left)

    def update(self, line, finished):
        info = self.info()
        if info is None:
            return False
        # Always position cursor at the start of its *current* physical row;
        # never write a long progress line that causes a second physical row.
        pos = self.COORD(0, info.dwCursorPosition.Y)
        if not self.kernel.SetConsoleCursorPosition(self.handle, pos):
            return False
        written = self.ctypes.c_ulong(0)
        # Clear any previous characters left by a longer update.
        self.kernel.FillConsoleOutputCharacterW(self.handle, ' ',
            info.dwSize.X - 1, pos, self.ctypes.byref(written))
        self.kernel.SetConsoleCursorPosition(self.handle, pos)
        line = line[:self.width()]
        if not self.kernel.WriteConsoleW(self.handle, line, len(line),
                                         self.ctypes.byref(written), None):
            return False
        if finished:
            self.kernel.WriteConsoleW(self.handle, '\r\n', 2,
                                       self.ctypes.byref(written), None)
        return True

    def close(self):
        if self._owned and self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
            self._owned = False


class Reporter:
    """Exactly one physical console row per phase; no newline per update.

    On Windows, use native console cursor positioning rather than relying on
    carriage returns being forwarded through PowerShell. When there is no
    interactive console, emit only the final line (never flood a log).
    """
    def __init__(self, stream=None, console=None, width=None):
        self.stream = stream if stream is not None else sys.stdout
        self.console = console
        if console is None and stream is None and os.name == 'nt':
            try:
                self.console = _WindowsConsole()
            except OSError:
                pass
        self.width_override = width
        self.label = None
        self.last_report_time = 0.0
        self.last_width = 0
        self.completed_label = None
        self.interactive = self.console is not None or bool(getattr(self.stream, 'isatty', lambda: False)())

    def _width(self):
        import shutil
        if self.width_override is not None:
            return max(30, self.width_override)
        if self.console is not None:
            return self.console.width()
        return max(30, shutil.get_terminal_size(fallback=(80, 24)).columns - 2)

    @staticmethod
    def _compact(num):
        if num >= 1000000:
            return f'{num / 1000000:.1f}M'
        if num >= 1000:
            return f'{num / 1000:.1f}k'
        return str(num)

    def _line(self, label, current, total, elapsed, tail):
        ratio = min(1.0, current / total) if total else 1.0
        rate = current / max(elapsed, 0.001)
        remaining = max(0, total - current)
        eta = remaining / rate if rate > 0 else None
        # Reserve ample margin for narrow Windows PowerShell buffers.
        budget = self._width() - 2
        compact = (f' {ratio * 100:5.1f}% {self._compact(current)}/{self._compact(total)}'
                   f' faltan={self._compact(remaining)}'
                   f' {self._compact(int(rate))}/s ETA={fmt_time(eta)[-8:]}')
        # Reused/pending counts are crucial; display them if they fit.
        short_tail = tail.replace('reusadas=', 'reus=').replace('sin_etiqueta=', 'pend=')
        bar_width = max(6, min(24, budget - len(label) - len(compact) - len(short_tail) - 8))
        count = round(ratio * bar_width)
        prefix = f'{label:<9} [{"█" * count}{"░" * (bar_width - count)}]'
        line = prefix + compact
        if len(line) + 1 + len(short_tail) <= budget:
            line += ' ' + short_tail
        # Keep the physical line strictly shorter than the visible console width.
        return line[:budget]

    def update(self, label, current, total, started, tail='', force=False):
        now = time.monotonic()
        finished = current >= total
        if finished and self.completed_label == label:
            return
        if not force and not finished and now - self.last_report_time < 0.2:
            return
        line = self._line(label, current, total, max(now - started, 0.001), tail)
        if self.console is not None:
            if not self.console.update(line, finished):
                raise OSError('Could not render progress on Windows console')
        elif self.interactive:
            # For normal Unix terminals. Windows uses native console API above.
            self.stream.write('\r' + line + ' ' * max(0, self.last_width - len(line)))
            if finished:
                self.stream.write('\n')
            self.stream.flush()
            self.last_width = len(line)
        elif finished:
            # Redirected output has no redraw semantics. One final line only.
            self.stream.write(line + '\n')
            self.stream.flush()
        self.completed_label = label if finished else None
        self.last_report_time = now
        self.label = None if finished else label
        if finished:
            self.last_width = 0


def q(name):
    return '"' + name.replace('"', '""') + '"'


def table_columns(conn, database, table):
    return {r[1] for r in conn.execute(f'PRAGMA {q(database)}.table_info({q(table)})')}


def check_schema(conn, database, is_mix=False):
    required = set(POSITION_FIELDS + FIELDS)
    if is_mix:
        required = {'id', 'fen', *FIELDS}
    else:
        games = table_columns(conn, database, 'games')
        missing_games = set(GAME_FIELDS) - games
        if missing_games:
            raise ValueError(f'--in lacks games columns: {sorted(missing_games)}')
    positions = table_columns(conn, database, 'positions')
    missing = required - positions
    if missing:
        raise ValueError(f'{database} lacks positions columns: {sorted(missing)}')


def build_mix_index(conn, batch, reporter):
    total = conn.execute('SELECT count(*) FROM mix.positions').fetchone()[0]
    labeled = conn.execute('''SELECT count(*) FROM mix.positions
        WHERE teacher_at IS NOT NULL AND teacher_value IS NOT NULL''').fetchone()[0]
    print(f'🔎 MIX posiciones={total:,} etiquetadas_completas={labeled:,} '
          f'sin_etiqueta={total-labeled:,}', flush=True)
    # A temporary on-disk B-tree: no source mutation and no index residue in output.
    conn.execute('PRAGMA temp_store=FILE')
    conn.execute('''CREATE TEMP TABLE mix_lookup (
        fen TEXT PRIMARY KEY,
        teacher_uci TEXT, teacher_cp INTEGER, teacher_mate INTEGER,
        teacher_value REAL, teacher_depth INTEGER, teacher_at TEXT,
        source_id INTEGER NOT NULL
    ) WITHOUT ROWID''')
    # Rank multiple labels for same exact FEN by depth, then source row ID.
    # Conflict handling is deterministic; no labels are synthesized or averaged.
    sql = '''INSERT INTO temp.mix_lookup
        (fen, teacher_uci, teacher_cp, teacher_mate, teacher_value,
         teacher_depth, teacher_at, source_id)
        SELECT fen, teacher_uci, teacher_cp, teacher_mate, teacher_value,
               teacher_depth, teacher_at, id
        FROM mix.positions
        WHERE id > ? AND id <= ? AND teacher_at IS NOT NULL AND teacher_value IS NOT NULL
          AND fen IS NOT NULL AND trim(fen) <> '' AND 1
        ON CONFLICT(fen) DO UPDATE SET
          teacher_uci=excluded.teacher_uci, teacher_cp=excluded.teacher_cp,
          teacher_mate=excluded.teacher_mate, teacher_value=excluded.teacher_value,
          teacher_depth=excluded.teacher_depth, teacher_at=excluded.teacher_at,
          source_id=excluded.source_id
        WHERE COALESCE(excluded.teacher_depth,-1) > COALESCE(mix_lookup.teacher_depth,-1)
          OR (COALESCE(excluded.teacher_depth,-1) = COALESCE(mix_lookup.teacher_depth,-1)
              AND excluded.source_id > mix_lookup.source_id)'''
    start = time.monotonic()
    processed = 0
    last_id = 0
    reporter.update('INDEX MIX', 0, total, start, force=True)
    while processed < total:
        ids = conn.execute('SELECT id FROM mix.positions WHERE id > ? ORDER BY id LIMIT ?',
                           (last_id, batch)).fetchall()
        if not ids:
            raise RuntimeError('Mix row count changed while building index')
        end = ids[-1][0]
        conn.execute(sql, (last_id, end))
        processed += len(ids)
        last_id = end
        reporter.update('INDEX MIX', processed, total, start)
    reporter.update('INDEX MIX', processed, total, start, force=True)
    unique = conn.execute('SELECT count(*) FROM temp.mix_lookup').fetchone()[0]
    print(f'✅ MIX índice FEN únicas={unique:,}; duplicadas etiquetadas={labeled-unique:,}; '
          f'criterio=mayor depth, luego mayor id', flush=True)
    return unique


def copy_games(conn, batch, reporter):
    total = conn.execute('SELECT count(*) FROM src.games').fetchone()[0]
    fields = ', '.join(q(f) for f in GAME_FIELDS)
    start = time.monotonic()
    last_id = 0
    count = 0
    reporter.update('PARTIDAS', 0, total, start, force=True)
    while count < total:
        ids = conn.execute('SELECT id FROM src.games WHERE id > ? ORDER BY id LIMIT ?',
                           (last_id, batch)).fetchall()
        if not ids:
            raise RuntimeError('Input games changed while copying')
        end = ids[-1][0]
        conn.execute(f'''INSERT INTO main.games({fields})
            SELECT {fields} FROM src.games WHERE id>? AND id<=? ORDER BY id''', (last_id, end))
        count += len(ids)
        last_id = end
        reporter.update('PARTIDAS', count, total, start)
    reporter.update('PARTIDAS', count, total, start, force=True)
    return total


def copy_positions(conn, batch, reporter):
    total = conn.execute('SELECT count(*) FROM src.positions').fetchone()[0]
    input_cols = POSITION_FIELDS + FIELDS
    allfields = ', '.join(q(f) for f in input_cols)
    # Base information comes from src, annotation fields come EXCLUSIVELY from mix.
    sourcecols = ', '.join('p.' + q(f) for f in POSITION_FIELDS)
    labelcols = ', '.join('m.' + q(f) for f in FIELDS)
    insert = f'''INSERT INTO main.positions({allfields})
        SELECT {sourcecols}, {labelcols}
        FROM src.positions p LEFT JOIN temp.mix_lookup m ON m.fen=p.fen
        WHERE p.id>? AND p.id<=? ORDER BY p.id'''
    summary = '''SELECT count(*), count(m.fen) FROM src.positions p
        LEFT JOIN temp.mix_lookup m ON m.fen=p.fen
        WHERE p.id>? AND p.id<=?'''
    start = time.monotonic()
    last_id = 0
    count = reused = 0
    reporter.update('MEZCLA', 0, total, start, 'reusadas=0 pendientes=0', force=True)
    while count < total:
        ids = conn.execute('SELECT id FROM src.positions WHERE id>? ORDER BY id LIMIT ?',
                           (last_id, batch)).fetchall()
        if not ids:
            raise RuntimeError('Input positions changed while copying')
        end = ids[-1][0]
        n, matched = conn.execute(summary, (last_id, end)).fetchone()
        with conn:
            conn.execute(insert, (last_id, end))
        count += n
        reused += matched
        last_id = end
        reporter.update('MEZCLA', count, total, start,
                        f'reusadas={reused:,} sin_etiqueta={count-reused:,}')
    reporter.update('MEZCLA', count, total, start,
                    f'reusadas={reused:,} sin_etiqueta={count-reused:,}', force=True)
    return count, reused


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Mix labels from --mix onto --in by exact FEN; write teacher-ready --out')
    parser.add_argument('--in', dest='source', required=True, help='Source SQLite .pb DB (games/positions)')
    parser.add_argument('--mix', required=True, help='SQLite .pb DB with existing teacher labels')
    parser.add_argument('--out', required=True, help='New SQLite .pb DB (never overwrites input)')
    parser.add_argument('--batch', type=int, default=10000, help='Batch size (default: 10000)')
    parser.add_argument('--version', action='version', version=f'mixer.py v{VERSION}')
    args = parser.parse_args(argv)
    if args.batch < 1:
        parser.error('--batch must be positive')
    paths = [Path(x).resolve() for x in (args.source, args.mix, args.out)]
    if len(set(paths)) != 3:
        parser.error('--in, --mix and --out must be three different paths')
    for p in paths[:2]:
        if not p.is_file():
            parser.error(f'Input database does not exist: {p}')
    if paths[2].exists():
        parser.error(f'Output exists; refusing to overwrite: {paths[2]}')
    paths[2].parent.mkdir(parents=True, exist_ok=True)
    temp_path = paths[2].with_name(paths[2].name + '.mixer.tmp')
    if temp_path.exists():
        parser.error(f'Temporary output exists; remove only after checking it: {temp_path}')
    started = time.monotonic()
    reporter = Reporter()
    print(f'🧬 mixer.py v{VERSION} FEN exact match; only teacher fields from MIX', flush=True)
    print(f'🗄️ IN={paths[0]} bytes={paths[0].stat().st_size:,}', flush=True)
    print(f'🗄️ MIX={paths[1]} bytes={paths[1].stat().st_size:,}', flush=True)
    print(f'🗄️ OUT={paths[2]} batch={args.batch:,}', flush=True)
    succeeded = False
    try:
        with closing(sqlite3.connect(str(temp_path), timeout=60)) as conn:
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=60000')
            conn.execute('PRAGMA journal_mode=DELETE')
            # Windows: ordinary absolute paths avoid SQLite URI parsing ambiguities.
            # The input aliases are never written to by this program.
            conn.execute('ATTACH DATABASE ? AS src', (str(paths[0]),))
            conn.execute('ATTACH DATABASE ? AS mix', (str(paths[1]),))
            check_schema(conn, 'src')
            check_schema(conn, 'mix', is_mix=True)
            schema(conn)
            build_mix_index(conn, args.batch, reporter)
            games = copy_games(conn, args.batch, reporter)
            positions, reused = copy_positions(conn, args.batch, reporter)
            conn.commit()
            integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
            if integrity != 'ok':
                raise RuntimeError(f'Output integrity check failed: {integrity}')
            fk = conn.execute('PRAGMA foreign_key_check').fetchall()
            if fk:
                raise RuntimeError(f'Output foreign keys invalid: {fk[:4]}')
            actual = conn.execute('SELECT count(*) FROM main.positions').fetchone()[0]
            pending = conn.execute('''SELECT count(*) FROM main.positions
                WHERE teacher_at IS NULL OR teacher_value IS NULL''').fetchone()[0]
            if actual != positions or pending != positions-reused:
                raise RuntimeError('Final row/label count mismatch')
            print(f'✅ VERIFICACIÓN integrity=ok foreign_keys=ok '
                  f'games={games:,} positions={positions:,}', flush=True)
        os.replace(temp_path, paths[2])
        succeeded = True
        print(f'✅ MIXER OUT={paths[2]} bytes={paths[2].stat().st_size:,} '
              f'copiadas_con_etiqueta={reused:,} pendientes_teacher={positions-reused:,} '
              f'tiempo={fmt_time(time.monotonic()-started)}', flush=True)
    finally:
        if not succeeded and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as cleanup_error:
                print(f'⚠️ No se pudo eliminar temporal {temp_path}: {cleanup_error}',
                      file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
