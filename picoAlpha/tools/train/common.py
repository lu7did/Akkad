"""picoAlpha training data contract v0.1.1: SQLite database with .pb extension.
No relationship to protobuf or Berkeley DB; .pb is a user-selected suffix.
"""
import json
import sqlite3
import sys
import time

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS games (
 id INTEGER PRIMARY KEY, source_file TEXT NOT NULL, source_ordinal INTEGER NOT NULL,
 headers_json TEXT NOT NULL, result TEXT NOT NULL, start_fen TEXT NOT NULL,
 imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_file,source_ordinal)
);
CREATE TABLE IF NOT EXISTS positions (
 id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
 ply INTEGER NOT NULL, fen TEXT NOT NULL, played_uci TEXT NOT NULL,
 teacher_uci TEXT, teacher_cp INTEGER, teacher_mate INTEGER, teacher_value REAL,
 teacher_depth INTEGER, teacher_at TEXT,
 UNIQUE(game_id,ply)
);
CREATE INDEX IF NOT EXISTS idx_positions_game ON positions(game_id,ply);
CREATE INDEX IF NOT EXISTS idx_positions_teacher ON positions(teacher_value);
'''

def connect(path):
    c=sqlite3.connect(path,timeout=30)
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=30000')
    return c

def schema(c):
    c.executescript(SCHEMA)

def verify(c):
    needed={'games','positions'}
    have={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not needed<=have: raise ValueError('Database missing required tables: '+str(needed-have))

class _ProgressLine:
    """Progreso en una sola fila sin wrapping, incluso en PowerShell de 80 columnas.

    Los dispositivos redirigidos reciben solamente una línea de resumen al terminar.
    """
    def __init__(self, stream=None, columns=None):
        self.stream = stream if stream is not None else sys.stdout
        self.tty = bool(getattr(self.stream, 'isatty', lambda: False)())
        self.columns = columns  # Inyectable para pruebas; None = terminal real.
        self.last_length = 0
        self.active_label = None
        self.pending = ''

    def _width(self):
        # Reservar una columna: escribir en la última columna puede desplazar
        # automáticamente el cursor al renglón siguiente en consolas Windows.
        import shutil
        columns = self.columns if self.columns is not None else shutil.get_terminal_size((80, 24)).columns
        return max(1, int(columns) - 1)

    def _format(self, label, current, total, tail):
        total = max(0, int(total))
        current = max(0, min(int(current), total))
        fraction = (current / total) if total else 1.0
        cap = self._width() if self.tty else 120
        counter = f'{current:>{max(1,len(str(total)))}d}/{total:d}'
        label = str(label)[:14]
        prefix = f'{label:<12} ['
        suffix = f'] {fraction*100:6.2f}% {counter}'
        tail = str(tail).strip()
        # No rellenar el campo 'tail' si está ausente (como en teacher.py).
        reserved = len(prefix) + len(suffix) + (1 if tail else 0)
        bar_width = max(0, min(24, cap - reserved))
        if bar_width:
            filled = min(bar_width, round(bar_width*fraction))
            line = prefix + '█'*filled + '░'*(bar_width-filled) + suffix
        else:
            line = f'{label} {fraction*100:.2f}% {counter}'
        if tail:
            available = cap - len(line) - 1
            if available > 0:
                line += ' ' + tail[:available]
        return line[:cap]

    def update(self, label, current, total, tail=''):
        label = str(label)
        if self.active_label is not None and label != self.active_label:
            self.finish()
        self.active_label = label
        line = self._format(label, current, total, tail)
        if self.tty:
            cap = self._width()
            clearing = min(max(0, self.last_length - len(line)), max(0,cap-len(line)))
            self.stream.write('\r' + line + ' '*clearing)
            self.stream.flush()
            self.last_length = len(line) + clearing
        else:
            self.pending = line
        if int(current) >= int(total):
            self.finish()

    def finish(self):
        if self.active_label is None:
            return
        if self.tty:
            self.stream.write('\n')
        else:
            self.stream.write(self.pending + '\n')
        self.stream.flush()
        self.active_label = None
        self.last_length = 0
        self.pending = ''

_progress_line = _ProgressLine()

def progress(label, current, total, tail=''):
    """Reescribe la misma fila; sólo finaliza cuando termina la etapa."""
    _progress_line.update(label, current, total, tail)

def require_chess():
    try: import chess; import chess.pgn; return chess
    except ImportError as e: raise SystemExit('Install dependencies: python -m pip install -r requirements.txt') from e

def features(board):
    """780 sparse inputs: 12*64 relative pieces, 4 relative castling, 8 EP files."""
    chess=require_chess()
    own=board.turn
    out=[]
    for sq,piece in board.piece_map().items():
        ptype=piece.piece_type-1 + (0 if piece.color==own else 6)
        # exact transform in supplied network sketch: white a8=0; black rotated 180
        ix=(7-chess.square_rank(sq))*8+chess.square_file(sq)
        if not own: ix=63-ix
        out.append(ptype*64+ix)
    for flag,color,short in [(768,own,True),(769,own,False),(770,not own,True),(771,not own,False)]:
        if (board.has_kingside_castling_rights(color) if short else board.has_queenside_castling_rights(color)):
            out.append(flag)
    if board.ep_square is not None:
        f=chess.square_file(board.ep_square)
        out.append(772+(f if own else 7-f))
    return sorted(out)

def square_index(sq,turn):
    chess=require_chess()
    index=(7-chess.square_rank(sq))*8+chess.square_file(sq)
    return index if turn else 63-index

def move_indices(move,turn): return square_index(move.from_square,turn),square_index(move.to_square,turn)

def quant_params(): return 780*16+16+16*64*2
