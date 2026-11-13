"""Re-entrant Stockfish teacher. Invalid input FENs are removed, not fatal.

Only malformed board data are skipped. Engine/IO failures remain fatal so a bad
Stockfish process is never silently misreported as corrupt training data.
"""
import argparse
import math
import os
import shlex
import sys
from common import connect, verify, progress, require_chess


def teach_positions(db, chess, engine, limit_factory, depth, nodes=None, announce=print):
    total = db.execute('SELECT count(*) FROM positions').fetchone()[0]
    completed = labeled = removed = 0
    samples = []
    # An independent read cursor allows deletes/updates on the same connection.
    cursor = db.execute('SELECT id,fen FROM positions ORDER BY id')
    for position_id, fen in cursor:
        bad = None
        try:
            board = chess.Board(fen)
            if not board.is_valid():
                bad = 'board.is_valid()=False'
        except (ValueError, TypeError) as exc:
            bad = str(exc)
        if bad is not None:
            with db:
                db.execute('DELETE FROM positions WHERE id=?', (position_id,))
            removed += 1
            if len(samples) < 8:
                samples.append((position_id, fen, bad))
        else:
            if board.is_game_over(claim_draw=True):
                value = (0. if board.is_stalemate() or board.is_insufficient_material()
                         or board.can_claim_draw() else -1.)
                best = cp = mate = None
            else:
                info = engine.analyse(board, limit_factory(depth=depth, nodes=nodes))
                pv = info.get('pv', [])
                best = pv[0].uci() if pv else None
                score = info['score'].pov(board.turn)
                mate = score.mate() if score.is_mate() else None
                cp = None if mate is not None else score.score()
                value = (1. if mate > 0 else -1.) if mate is not None else math.tanh(cp / 400.)
            with db:
                db.execute('''UPDATE positions SET teacher_uci=?,teacher_cp=?,teacher_mate=?,
                    teacher_value=?,teacher_depth=?,teacher_at=CURRENT_TIMESTAMP WHERE id=?''',
                    (best, cp, mate, value, depth, position_id))
            labeled += 1
        completed += 1
        if completed % 25 == 0 or completed == total:
            progress('Teaching', completed, total)
    # Output diagnostics after progress finishes; do not break its one-line bar.
    for position_id, fen, reason in samples:
        announce(f'⚠️ Removed invalid position id={position_id} reason={reason} fen={fen!r}')
    if removed > len(samples):
        announce(f'⚠️ ... and {removed-len(samples)} additional invalid positions removed')
    announce(f'✅ Teacher processed={completed}/{total} labeled={labeled} invalid_removed={removed}')
    return labeled, removed


def main():
    p = argparse.ArgumentParser(description='Re-label positions using Stockfish; delete malformed FEN rows')
    p.add_argument('--in', dest='source', required=True)
    p.add_argument('--engine', required=True, help='Path to Stockfish executable')
    p.add_argument('--args', default='', help='Extra command line arguments passed to engine')
    p.add_argument('--depth', type=int, default=10)
    p.add_argument('--nodes', type=int, default=None, help='Optional per-position node limit')
    a = p.parse_args()
    if a.depth <= 0: p.error('--depth must be positive')
    chess = require_chess()
    import chess.engine
    with connect(a.source) as db:
        verify(db)
        total = db.execute('SELECT count(*) FROM positions').fetchone()[0]
        if not total: p.error('Database contains no positions')
        command = [a.engine] + shlex.split(a.args, posix=(os.name != 'nt'))
        print('🧠 Engine:', repr(command), 'positions=', total, 'database=', os.path.abspath(a.source))
        engine = chess.engine.SimpleEngine.popen_uci(command)
        try:
            teach_positions(db, chess, engine, chess.engine.Limit, a.depth, a.nodes)
        finally:
            engine.quit()


if __name__ == '__main__':
    main()
