"""Import PGN mainlines and display exactly two fixed-position progress lines.

The preparatory count scans each PGN once using python-chess skip_game(), then
reads it a second time for import. No game is counted by file-size heuristics.
"""
import argparse
import glob
import json
import os
import sys

from common import connect, schema, require_chess


class TwoLineProgress:
    """Two stable lines; ANSI cursor-up only when stdout is a terminal."""
    BAR_WIDTH = 24
    FILE_WIDTH = 26

    def __init__(self, total_files, total_games, stream=None):
        self.stream = stream if stream is not None else sys.stdout
        self.terminal = bool(getattr(self.stream, 'isatty', lambda: False)())
        if self.terminal and os.name == 'nt' and not self._enable_windows_ansi():
            self.terminal = False
        self.file_digits = max(1, len(str(total_files)))
        self.game_digits = max(1, len(str(total_games)))
        self.rendered = False

    @staticmethod
    def _enable_windows_ansi():
        """Activate VT sequences in a standard Windows console if available."""
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint()
            return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)) and
                        kernel32.SetConsoleMode(handle, mode.value | 0x0004))
        except (AttributeError, OSError):
            return False

    @classmethod
    def bar(cls, current, total):
        fraction = 1.0 if total == 0 else min(1.0, current / total)
        filled = min(cls.BAR_WIDTH, int(fraction * cls.BAR_WIDTH + 0.5))
        return f'[{"█" * filled}{"░" * (cls.BAR_WIDTH - filled)}] {fraction * 100:6.2f}%'

    @classmethod
    def short_file(cls, path):
        name = os.path.basename(path) or '-'
        if len(name) > cls.FILE_WIDTH:
            name = '…' + name[-(cls.FILE_WIDTH-1):]
        return f'{name:<{cls.FILE_WIDTH}}'

    def lines(self, file_number, file_total, game_number, game_total, path):
        files = (f'📁 Archivos {self.bar(file_number, file_total)} '
                 f'{file_number:>{self.file_digits}d}/{file_total:>{self.file_digits}d} '
                 f'{self.short_file(path)}')
        games = (f'♟  Partidas {self.bar(game_number, game_total)} '
                 f'{game_number:>{self.game_digits}d}/{game_total:>{self.game_digits}d}')
        return files, games

    def update(self, file_number, file_total, game_number, game_total, path):
        first, second = self.lines(file_number, file_total, game_number, game_total, path)
        if self.terminal:
            if self.rendered:
                self.stream.write('\x1b[2A')
            self.stream.write(f'\r\x1b[2K{first}\n\r\x1b[2K{second}\n')
        self.rendered = True
        self.last_lines = first, second
        if self.terminal:
            self.stream.flush()

    def finish(self):
        if not self.rendered:
            return
        if not self.terminal:
            self.stream.write('\n'.join(self.last_lines) + '\n')
        self.stream.flush()


def count_games(path, chess):
    """Count PGN games without building a move tree; parser matches read_game boundaries."""
    count = 0
    with open(path, 'r', encoding='utf-8-sig', errors='replace') as stream:
        while chess.pgn.skip_game(stream):
            count += 1
    return count


def main():
    p = argparse.ArgumentParser(description='Append PGN games to SQLite .pb; display exactly two progress lines')
    p.add_argument('--in', dest='source', required=True, help='PGN glob, e.g. C:/games/c*.pgn')
    p.add_argument('--out', required=True, help='SQLite .pb database')
    a = p.parse_args()
    chess = require_chess()
    files = sorted(f for f in glob.glob(a.source, recursive=True) if os.path.isfile(f))
    if not files:
        p.error('No PGN files matched --in')

    totals = [count_games(path, chess) for path in files]
    tracker = TwoLineProgress(len(files), max(totals, default=0))
    tracker.update(0, len(files), 0, totals[0], files[0])
    invalid_games = 0
    try:
        with connect(a.out) as db:
            schema(db)
            for file_number, (path, expected) in enumerate(zip(files, totals), 1):
                tracker.update(file_number - 1, len(files), 0, expected, path)
                game_no = 0
                source = os.path.normcase(os.path.abspath(path))
                with open(path, 'r', encoding='utf-8-sig', errors='replace') as stream:
                    while True:
                        try:
                            game = chess.pgn.read_game(stream)
                        except (ValueError, UnicodeError) as error:
                            raise ValueError(f'Cannot parse PGN {path}, game {game_no+1}: {error}') from error
                        if game is None:
                            break
                        game_no += 1
                        if not game.errors:
                            exists = db.execute(
                                'SELECT id FROM games WHERE source_file=? AND source_ordinal=?',
                                (source, game_no)).fetchone()
                            if not exists:
                                # Validate before writing any rows. Broken SetUp/FEN
                                # headers and illegal moves must not poison teacher DB.
                                try:
                                    board = game.board()
                                    if not board.is_valid():
                                        raise ValueError('invalid initial position')
                                    start_fen = board.fen(en_passant='fen')
                                    rows = []
                                    for ply, move in enumerate(game.mainline_moves(), 1):
                                        if move not in board.legal_moves:
                                            raise ValueError(f'illegal PGN move at ply {ply}: {move}')
                                        rows.append((ply, board.fen(en_passant='fen'), move.uci()))
                                        board.push(move)
                                        if not board.is_valid():
                                            raise ValueError(f'invalid position after ply {ply}')
                                except (ValueError, TypeError, AssertionError):
                                    invalid_games += 1
                                else:
                                    with db:
                                        cur = db.execute(
                                            'INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES(?,?,?,?,?)',
                                            (source, game_no, json.dumps(dict(game.headers), ensure_ascii=False),
                                             game.headers.get('Result', '*'), start_fen))
                                        db.executemany(
                                            'INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(?,?,?,?)',
                                            [(cur.lastrowid, *row) for row in rows])
                        else:
                            invalid_games += 1
                        # Count even a malformed or already-imported game as processed.
                        tracker.update(file_number - 1, len(files), game_no, expected, path)
                if game_no != expected:
                    raise RuntimeError(f'PGN changed during import: {path} (counted {expected}, read {game_no})')
                tracker.update(file_number, len(files), expected, expected, path)
    finally:
        tracker.finish()
    if invalid_games:
        print(f"⚠️ Skipped {invalid_games} malformed PGN games; no partial games imported")


if __name__ == '__main__':
    main()
