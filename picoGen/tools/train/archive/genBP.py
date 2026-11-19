"""Apply the EPD best move, then label the resulting position using Stockfish.

`games.start_fen` is the original EPD board. `positions.fen` is the board
after its chosen `bm`; `positions.played_uci` is that applied EPD move.
`teacher_cp` is Stockfish's evaluation of `positions.fen`, in its turn POV.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time

CREATE_SQL = '''
PRAGMA foreign_keys=ON;
CREATE TABLE games (
 id INTEGER PRIMARY KEY, source_file TEXT NOT NULL,
 source_ordinal INTEGER NOT NULL, headers_json TEXT NOT NULL,
 result TEXT NOT NULL, start_fen TEXT NOT NULL,
 imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_file, source_ordinal));
CREATE TABLE positions (
 id INTEGER PRIMARY KEY,
 game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
 ply INTEGER NOT NULL, fen TEXT NOT NULL, played_uci TEXT NOT NULL,
 teacher_uci TEXT, teacher_cp INTEGER, teacher_mate INTEGER,
 teacher_value REAL, teacher_depth INTEGER, teacher_at TEXT,
 UNIQUE(game_id, ply));
CREATE INDEX idx_positions_game ON positions(game_id, ply);
CREATE INDEX idx_positions_teacher ON positions(teacher_value);
'''


def progress(done, total, generated, label='GenBP'):
    """Single physical line, terminal-width aware, fixed-width counters."""
    total = max(0, int(total))
    done = max(0, min(int(done), total))
    digits = max(1, len(str(total)))
    fraction = 1.0 if total == 0 else done / total
    tty = bool(getattr(sys.stdout, 'isatty', lambda: False)())
    if not tty and done < total:
        return
    cols = shutil.get_terminal_size((80, 24)).columns
    # Two spare columns (one for auto-wrap avoidance). The textual suffix is fixed.
    suffix = f' {fraction * 100:6.2f}% creados={generated:>{digits}d}/{total:>{digits}d}'
    prefix = f'{label:<7} ['
    width = max(1, min(24, cols - len(prefix) - len(suffix) - 4))
    filled = round(width * fraction)
    line = prefix + '█' * filled + '░' * (width - filled) + ']' + suffix
    if tty:
        sys.stdout.write('\r' + line + ('\n' if done == total else ''))
    else:
        sys.stdout.write(line + '\n')
    sys.stdout.flush()


def load_epd_records(epd_path):
    """Parse EPD's mandatory four FEN fields; operations remain opaque metadata.

    1-based line numbering is retained. The returned list is bounded by the EPD
    input, not by the size of SQLite's output.
    """
    records = []
    with epd_path.open('r', encoding='utf-8-sig') as stream:
        for line_no, raw in enumerate(stream, 1):
            line = raw.strip().strip('\x00')
            if not line or line.startswith('#') or line.startswith('%'):
                continue
            fields = line.split(';', 1)[0].split()
            if len(fields) < 4:
                records.append((line_no, None, line))
            else:
                records.append((line_no, ' '.join(fields[:4]) + ' 0 1', line))
    return records


def orthodox_material_possible(board, chess):
    """Necessary, not sufficient, orthodoxy constraint: promotions consume pawns."""
    for color in (chess.WHITE, chess.BLACK):
        pawns = len(board.pieces(chess.PAWN, color))
        if pawns > 8:
            return False
        extra = sum(max(0, len(board.pieces(pt, color)) - n) for pt, n in (
            (chess.KNIGHT, 2), (chess.BISHOP, 2),
            (chess.ROOK, 2), (chess.QUEEN, 1)))
        if extra > 8 - pawns:
            return False
    return True


def epd_after_best_move(raw, chess):
    """Parse EPD bm moves as SAN, apply the first legal alternative, return both boards."""
    before, operations = chess.Board.from_epd(raw)
    if not before.is_valid() or not orthodox_material_possible(before, chess):
        raise ValueError('invalid or non-orthodox EPD position')
    candidates = operations.get('bm')
    if isinstance(candidates, chess.Move):
        candidates = [candidates]
    if not candidates:
        raise ValueError('EPD without bm')
    candidates = list(candidates)
    if any(move not in before.legal_moves for move in candidates):
        raise ValueError('EPD bm contains illegal moves')
    # In a suite with alternative best moves, the first solution is selected.
    chosen = candidates[0]
    after = before.copy(stack=False)
    after.push(chosen)
    if not after.is_valid():
        raise ValueError('position after bm is invalid')
    return before, after, chosen, candidates, operations


def parse_info(info, board, chess):
    if not isinstance(info, dict) or 'score' not in info:
        raise ValueError('UCI analysis lacks score')
    pov = info['score'].pov(board.turn)
    mate = pov.mate() if pov.is_mate() else None
    cp = None if mate is not None else pov.score()
    if mate is not None:
        if isinstance(mate, bool) or not isinstance(mate, int):
            raise ValueError('invalid mate score')
        value = 1.0 if mate > 0 else -1.0 if mate < 0 else 0.0
    else:
        if cp is None or isinstance(cp, bool) or not isinstance(cp, (int, float)) or not math.isfinite(cp):
            raise ValueError('nonfinite or absent centipawn score')
        cp = int(cp)
        value = math.tanh(cp / 400.0)
    pv = info.get('pv')
    move = pv[0] if isinstance(pv, (list, tuple)) and pv else None
    if move is not None and move not in board.legal_moves:
        raise ValueError('UCI principal move is illegal')
    return move.uci() if move else None, cp, mate, value


def run(source, target, engine_path, depth=10, nodes=None):
    import chess
    import chess.engine
    source = Path(source).expanduser().resolve()
    target = Path(target).expanduser().resolve()
    engine_path = Path(engine_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f'EPD de entrada inexistente: {source}')
    if not engine_path.is_file():
        raise ValueError(f'Stockfish inexistente: {engine_path}')
    if source == target:
        raise ValueError('--in y --out deben tener rutas distintas')
    if depth <= 0 or (nodes is not None and nodes <= 0):
        raise ValueError('--depth y --nodes deben ser positivos')
    if not target.parent.is_dir():
        raise ValueError(f'Directorio de salida inexistente: {target.parent}')
    records = load_epd_records(source)
    if not records:
        raise ValueError('El EPD no contiene posiciones')
    total = len(records)
    digits = len(str(total))
    print(f'🧬 genBP EPD={source} posiciones={total} DB={target} Stockfish={engine_path} depth={depth} nodes={nodes}', flush=True)
    fd, temp_name = tempfile.mkstemp(prefix='.' + target.stem + '.', suffix='.pb', dir=target.parent)
    os.close(fd)
    tmp = Path(temp_name)
    created = ignored = 0
    failures = []
    done = 0
    engine = None
    try:
        with closing(sqlite3.connect(tmp)) as db:
            db.executescript(CREATE_SQL)
            try:
                engine = chess.engine.SimpleEngine.popen_uci(str(engine_path))
                limit = chess.engine.Limit(depth=depth, nodes=nodes)
                for done, (line_no, fen, raw) in enumerate(records, 1):
                    try:
                        if fen is None:
                            raise ValueError('EPD lacks four position fields')
                        before, after, chosen, candidates, operations = epd_after_best_move(raw, chess)
                        if after.is_game_over(claim_draw=True):
                            # Terminal child has no numeric centipawn score. Preserve
                            # the example as a mate/draw value, never invent cp.
                            cp = None
                            mate = -1 if after.is_checkmate() else None
                            value = -1.0 if after.is_checkmate() else 0.0
                            teacher_move = None
                        else:
                            for attempt in range(2):
                                try:
                                    info = engine.analyse(after, limit)
                                    teacher_move, cp, mate, value = parse_info(info, after, chess)
                                    break
                                except (chess.engine.EngineTerminatedError, OSError,
                                        EOFError, BrokenPipeError):
                                    if attempt:
                                        raise
                                    try:
                                        engine.quit()
                                    except Exception:
                                        pass
                                    engine = chess.engine.SimpleEngine.popen_uci(str(engine_path))
                        headers = json.dumps({
                            'EPD_line': line_no, 'EPD': raw,
                            'label_source': 'Stockfish',
                            'position_contract': 'epd-bm-result-v1',
                            'bm_selected_uci': chosen.uci(),
                            'bm_alternatives_uci': [m.uci() for m in candidates],
                            'epd_id': operations.get('id'),
                        }, ensure_ascii=False)
                        gid = db.execute('INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) '
                                         'VALUES(?,?,?,?,?)',
                                         (str(source), line_no, headers, '*', before.fen(en_passant='fen'))).lastrowid
                        db.execute('INSERT INTO positions(game_id,ply,fen,played_uci,teacher_uci,teacher_cp,'
                                   'teacher_mate,teacher_value,teacher_depth,teacher_at) '
                                   'VALUES(?,?,?,?,?,?,?,?,?,?)',
                                   (gid, 1, after.fen(en_passant='fen'), chosen.uci(),
                                    teacher_move, cp, mate, value, depth,
                                    datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')))
                        created += 1
                        db.commit()
                    except (ValueError, chess.engine.EngineError, chess.engine.EngineTerminatedError,
                            OSError, EOFError, BrokenPipeError) as exc:
                        ignored += 1
                        failures.append((line_no, str(exc)))
                    if done % 10 == 0 or done == total:
                        progress(done, total, created)
            finally:
                if engine is not None:
                    try:
                        engine.quit()
                    except Exception:
                        pass
        # Source is never touched; only the complete, closed temporary database is replaced.
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    for line_no, reason in failures[:12]:
        print(f'⚠️ EPD line={line_no} ignored: {reason}', flush=True)
    if len(failures) > 12:
        print(f'⚠️ ... y otras {len(failures)-12} posiciones ignoradas', flush=True)
    print(f'✅ genBP output={target} generated={created}/{total} ignored={ignored}', flush=True)
    return created, ignored


def main(argv=None):
    parser = argparse.ArgumentParser(description='EPD -> picoAlpha-compatible labeled SQLite .pb (Stockfish)')
    parser.add_argument('--in', dest='source', required=True, help='Archivo EPD con posiciones de ajedrez')
    parser.add_argument('--out', required=True, help='Database SQLite .pb de salida (se sobrescribe al finalizar)')
    parser.add_argument('--stockfish', required=True, help='Ruta al ejecutable de Stockfish')
    parser.add_argument('--depth', type=int, default=10, help='Profundidad Stockfish (default 10)')
    parser.add_argument('--nodes', type=int, default=None, help='Limite opcional de nodos por posicion')
    args = parser.parse_args(argv)
    try:
        run(args.source, args.out, args.stockfish, depth=args.depth, nodes=args.nodes)
    except KeyboardInterrupt:
        print('\n⚠️ genBP interrumpido: la salida anterior permanece intacta', file=sys.stderr)
        return 130
    except (ValueError, OSError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    sys.exit(main())
