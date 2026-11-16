"""Stockfish labeling with durable SQLite checkpoints and recoverable engine exits.

--resume skips rows that already have both teacher_at and teacher_value. Each
successful label is committed immediately, so unexpected interpreter/engine
termination cannot lose the last successfully completed position.
"""
import argparse
import math
import os
import shlex
import sys
import time
from common import connect, verify, progress, require_chess


class EnginePositionFailure(RuntimeError):
    """A UCI process repeatedly crashed while analysing one position."""


class RestartableEngine:
    """Own a UCI process. Restart it on transport/process failure, not bad data."""

    def __init__(self, factory, command, recoverable_errors, retries=3,
                 delay=1.0, reporter=None):
        if retries < 0:
            raise ValueError('retries must be >= 0')
        self.factory = factory
        self.command = command
        self.recoverable_errors = tuple(recoverable_errors)
        self.retries = retries
        self.delay = delay
        self.reporter = reporter or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self.engine = None
        self.restarts = 0
        self.recoveries = 0
        self._spawn()

    def _spawn(self):
        for attempt in range(self.retries + 1):
            try:
                self.engine = self.factory(self.command)
                return
            except self.recoverable_errors as exc:
                if attempt == self.retries:
                    raise RuntimeError(f'Stockfish could not start after {attempt+1} attempts') from exc
                self.reporter(f'⚠️ Stockfish startup failed ({type(exc).__name__}); retry {attempt+1}/{self.retries}')
                if self.delay:
                    time.sleep(self.delay)

    def _close_dead(self):
        old, self.engine = self.engine, None
        if old is not None:
            try:
                old.quit()
            except Exception:
                # A dead UCI event loop cannot service quit; do not mask the
                # original failure with EngineTerminatedError from cleanup.
                pass

    def analyse(self, board, limit):
        for attempt in range(self.retries + 1):
            try:
                if self.engine is None:
                    self._spawn()
                return self.engine.analyse(board, limit)
            except self.recoverable_errors as exc:
                if attempt == self.retries:
                    # Quarantine only THIS position. A fresh engine will be
                    # started lazily for the next position, not reusing a dead loop.
                    self._close_dead()
                    raise EnginePositionFailure(
                        f'Stockfish failed {attempt+1} times at this position '
                        f'({type(exc).__name__}: {exc})'
                    ) from exc
                self.reporter(f'⚠️ Stockfish terminated ({type(exc).__name__}); '
                              f'restarting {attempt+1}/{self.retries} and retrying position')
                self._close_dead()
                if self.delay:
                    time.sleep(self.delay)
                self._spawn()
                self.restarts += 1
        raise AssertionError('unreachable')

    def close(self):
        self._close_dead()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class BadEngineResult(ValueError):
    """UCI analysis returned no usable numerical score or an invalid principal line."""


def interpret_analysis(info, board):
    """Validate UCI payload before persisting. Never treat bad output as a label."""
    if not isinstance(info, dict):
        raise BadEngineResult('analyse() did not return a dictionary')
    try:
        score = info['score'].pov(board.turn)
        if score is None:
            raise BadEngineResult('missing score POV')
        mate = score.mate() if score.is_mate() else None
        cp = None if mate is not None else score.score()
        if mate is not None:
            if isinstance(mate, bool) or not isinstance(mate, int):
                raise BadEngineResult('invalid mate score')
            value = 1.0 if mate > 0 else (-1.0 if mate < 0 else 0.0)
        else:
            if cp is None or isinstance(cp, bool) or not isinstance(cp, (int, float)) or not math.isfinite(cp):
                raise BadEngineResult('missing or nonfinite centipawn score')
            value = math.tanh(cp / 400.0)
        pv = info.get('pv', ())
        if pv is None or not isinstance(pv, (list, tuple)):
            raise BadEngineResult('invalid PV type')
        best = None
        if pv:
            move = pv[0]
            best = move.uci()
            if not isinstance(best, str) or len(best) not in (4, 5):
                raise BadEngineResult('invalid UCI best move')
            legal = getattr(board, 'legal_moves', None)
            if legal is not None and move not in legal:
                raise BadEngineResult('principal variation begins with an illegal move')
        return best, cp, mate, value
    except BadEngineResult:
        raise
    except (KeyError, IndexError, TypeError, ValueError, AttributeError, OverflowError) as exc:
        raise BadEngineResult(f'malformed UCI analysis: {type(exc).__name__}: {exc}') from exc




def impossible_standard_material(board, chess):
    """Necessary (not sufficient) reachability test for orthodox chess.

    A promoted piece consumes a pawn, so material beyond the initial allotment
    cannot exceed the number of missing pawns for either side. This rejects
    the observed 7 bishops + 8 pawns crash without invoking the UCI engine.
    """
    limits = ((chess.QUEEN, 1), (chess.ROOK, 2),
              (chess.BISHOP, 2), (chess.KNIGHT, 2))
    for color in (chess.WHITE, chess.BLACK):
        pawns = len(board.pieces(chess.PAWN, color))
        if pawns > 8:
            return True
        promoted_minimum = sum(
            max(0, len(board.pieces(piece, color)) - starting)
            for piece, starting in limits
        )
        if promoted_minimum > 8 - pawns:
            return True
    return False


def probe_standard_engine(chess, engine, limit_factory, announce):
    """Distinguish a batch of bad positions from a dead/broken engine.

    This is a *control* run on orthodox start FEN. It does not label, mutate,
    or persist anything. A failure here is systemic and stops the job.
    """
    standard_fen = getattr(chess, 'STARTING_FEN',
                           'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
    board = chess.Board(standard_fen)
    try:
        response = engine.analyse(board, limit_factory(depth=1))
        interpret_analysis(response, board)
    except (EnginePositionFailure, BadEngineResult, RuntimeError, OSError) as exc:
        raise RuntimeError(
            'Stockfish failed on multiple consecutive positions AND on an '
            'orthodox starting-position control. Stopping; investigate the '
            'engine rather than mass-quarantining records.'
        ) from exc
    announce('✅ Stockfish control OK after consecutive problem positions; continuing')

def _format_teacher_eta(seconds):
    """Fixed-width HHHHHH:MM:SS, including during large, multi-day jobs."""
    if seconds is None or not math.isfinite(seconds):
        return '------:--:--'
    n = max(0, int(seconds))
    return f'{min(n // 3600, 999999):06d}:{(n // 60) % 60:02d}:{n % 60:02d}'


def teach_positions(db, chess, engine, limit_factory, depth, nodes=None,
                    announce=print, resume=False):
    """Scan all rows; skip labeled ones without evaluation; return (labeled, removed)."""
    total = db.execute('SELECT count(*) FROM positions').fetchone()[0]
    # Scan EVERY row in ascending id order. A resumed job fast-forwards over
    # previously labeled positions without opening a board or invoking Stockfish.
    # This makes the progress numerator verifiable against the original count.
    # Preserve repeatedly crashing positions for diagnosis; do not delete
    # potentially valid positions merely because the UCI process died.
    db.execute("""CREATE TABLE IF NOT EXISTS teacher_quarantine (
        position_id INTEGER PRIMARY KEY, fen TEXT NOT NULL,
        reason TEXT NOT NULL, attempts INTEGER NOT NULL,
        quarantined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.commit()
    existing = db.execute('''SELECT count(*) FROM positions
        WHERE teacher_at IS NOT NULL AND teacher_value IS NOT NULL''').fetchone()[0] if resume else 0
    cursor = db.execute('''SELECT id, fen, teacher_at, teacher_value
        FROM positions ORDER BY id''')
    quarantine_ids = {row[0] for row in db.execute(
        'SELECT q.position_id FROM teacher_quarantine q '
        'INNER JOIN positions p ON p.id=q.position_id')}
    quarantined_before = len(quarantine_ids)
    pending = total - existing - (quarantined_before if resume else 0)
    labeled = removed = scanned = skipped = bad_engine = quarantined_now = 0
    consecutive_failures = 0
    max_consecutive_failures = 5
    samples = []
    work_started = None
    def report_progress():
        # El fast-forward no consume tiempo de Stockfish y no se usa para
        # extrapolar el ritmo de procesamiento. El denominador es el trabajo
        # que efectivamente faltaba al iniciar esta ejecución.
        completed = labeled + removed + quarantined_now
        if work_started is None or completed == 0:
            remaining = None
        else:
            elapsed = max(0.001, time.monotonic() - work_started)
            remaining = elapsed * max(0, pending - completed) / completed
        progress('Teaching', scanned, total, tail='ETA=' + _format_teacher_eta(remaining))

    announce(f'🧠 Teacher resume={resume} total={total} already_labeled={existing} quarantined={quarantined_before} pending={pending}')
    # The initial 0/total is deliberate. Fast-forward progress counts every
    # row actually inspected, rather than jumping to the pre-counted total.
    report_progress()
    for position_id, fen, teacher_at, teacher_value in cursor:
        scanned += 1
        if resume and ((teacher_at is not None and teacher_value is not None) or
                       position_id in quarantine_ids):
            skipped += 1
            # Scan progress is throttled to avoid terminal I/O dominating a
            # multi-million-position fast-forward. Fixed-width single row.
            if scanned % 2500 == 0 or scanned == total:
                report_progress()
            continue
        if work_started is None:
            work_started = time.monotonic()
        bad = None
        try:
            board = chess.Board(fen)
            if not board.is_valid():
                bad = 'board.is_valid()=False'
            elif hasattr(board, 'pieces') and impossible_standard_material(board, chess):
                bad = 'impossible material for orthodox chess (excess promoted pieces)' 
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
                # If engine dies, RestartableEngine restarts and retries only
                # THIS position; no DB change is made before analysis succeeds.
                try:
                    info = engine.analyse(board, limit_factory(depth=depth, nodes=nodes))
                except EnginePositionFailure as exc:
                    # Do not silently delete a potentially good chess position.
                    # A fresh process will start on the next position.
                    with db:
                        db.execute('''INSERT OR REPLACE INTO teacher_quarantine(position_id,fen,reason,attempts,quarantined_at)
                            VALUES(?,?,?,?,CURRENT_TIMESTAMP)''',
                            (position_id, fen, str(exc), getattr(engine, 'retries', 3) + 1))
                    quarantined_now += 1
                    consecutive_failures += 1
                    announce(f'⚠️ Stockfish crash quarantined position id={position_id} '
                             f'consecutive_failures={consecutive_failures}: {exc}')
                    if consecutive_failures >= max_consecutive_failures:
                        # A whole nonstandard game may have several contiguous
                        # positions that kill Stockfish. Test an orthodox control
                        # before deciding the *engine* itself is broken.
                        probe_standard_engine(chess, engine, limit_factory, announce)
                        consecutive_failures = 0
                    if scanned % 25 == 0 or scanned == total:
                        report_progress()
                    continue
                consecutive_failures = 0
                try:
                    best, cp, mate, value = interpret_analysis(info, board)
                except BadEngineResult as exc:
                    # The response is not a useful Stockfish label. Do not
                    # confuse it with a transport failure: skip just this row.
                    with db:
                        db.execute('DELETE FROM positions WHERE id=?', (position_id,))
                    removed += 1
                    bad_engine += 1
                    if len(samples) < 8:
                        samples.append((position_id, fen, f'bad Stockfish output: {exc}'))
                    if scanned % 25 == 0 or scanned == total:
                        report_progress()
                    continue
            with db:
                db.execute('''UPDATE positions SET teacher_uci=?,teacher_cp=?,teacher_mate=?,
                    teacher_value=?,teacher_depth=?,teacher_at=CURRENT_TIMESTAMP WHERE id=?''',
                    (best, cp, mate, value, depth, position_id))
                # A non-resume reprocessing may successfully recover a formerly
                # quarantined position. Remove its obsolete failure record.
                db.execute('DELETE FROM teacher_quarantine WHERE position_id=?', (position_id,))
            labeled += 1
        if scanned % 25 == 0 or scanned == total:
            report_progress()
    # A traversal must account for every row present at the start, including
    # invalid FENs which were deleted during this run.
    if scanned != total or skipped + labeled + removed + quarantined_now != total:
        raise RuntimeError(f'Teacher scan inconsistent: total={total} scanned={scanned} '
                           f'skipped={skipped} labeled={labeled} removed={removed} '
                           f'quarantined={quarantined_now}')
    for position_id, fen, reason in samples:
        announce(f'⚠️ Removed invalid position id={position_id} reason={reason} fen={fen!r}')
    if removed > len(samples):
        announce(f'⚠️ ... and {removed-len(samples)} additional invalid positions removed')
    announce(f'✅ Teacher scanned={scanned}/{total} pending={pending} skipped={skipped} '
             f'labeled={labeled} invalid_removed={removed} crash_quarantined={quarantined_now}')
    return labeled, removed


def main():
    p = argparse.ArgumentParser(description='Stockfish teacher with engine restart and checkpoint resume')
    p.add_argument('--in', dest='source', required=True)
    p.add_argument('--engine', required=True, help='Path to Stockfish executable')
    p.add_argument('--args', default='', help='Extra command line arguments passed to engine')
    p.add_argument('--depth', type=int, default=10)
    p.add_argument('--nodes', type=int, default=None, help='Optional per-position node limit')
    p.add_argument('--resume', action='store_true', help='Skip positions already labeled (teacher_value and teacher_at)')
    p.add_argument('--engine-retries', type=int, default=3, help='Maximum restarts per position (default: 3)')
    a = p.parse_args()
    if a.depth <= 0: p.error('--depth must be positive')
    if a.nodes is not None and a.nodes <= 0: p.error('--nodes must be positive')
    if a.engine_retries < 0: p.error('--engine-retries must be >= 0')
    chess = require_chess()
    import chess.engine
    with connect(a.source) as db:
        verify(db)
        total = db.execute('SELECT count(*) FROM positions').fetchone()[0]
        if not total: p.error('Database contains no positions')
        command = [a.engine] + shlex.split(a.args, posix=(os.name != 'nt'))
        print('🧠 Engine:', repr(command), 'positions=', total, 'database=', os.path.abspath(a.source))
        # Preserve initial engine initialization even in --resume mode.
        with RestartableEngine(chess.engine.SimpleEngine.popen_uci, command,
                               recoverable_errors=(chess.engine.EngineTerminatedError,
                                                   chess.engine.EngineError,
                                                   OSError, EOFError, BrokenPipeError, TimeoutError),
                               retries=a.engine_retries) as engine:
            teach_positions(db, chess, engine, chess.engine.Limit, a.depth, a.nodes,
                            resume=a.resume)
            if engine.restarts:
                print(f'⚙️ Stockfish automatic restarts={engine.restarts}')


if __name__ == '__main__':
    main()
