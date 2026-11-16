"""Read-only check of picoAlpha SQLite label consistency.

Contract of teacher.py: teacher_cp is side-to-move POV, teacher_value=tanh(teacher_cp/400).
For white POV, derive cp_white = teacher_cp * (+1 if FEN is white to move else -1).
Does not alter SQLite or checkpoint files.
"""
import argparse
import math
import sqlite3
from collections import Counter


def audit(path, limit=0, tolerance=1e-5):
    db = sqlite3.connect('file:' + __import__('pathlib').Path(path).resolve().as_posix() + '?mode=ro', uri=True)
    try:
        columns = {r[1] for r in db.execute('PRAGMA table_info(positions)')}
        required = {'id', 'fen', 'teacher_cp', 'teacher_value', 'teacher_mate'}
        if not required.issubset(columns):
            raise RuntimeError('Missing columns: ' + ', '.join(sorted(required - columns)))
        sql = ('SELECT id,fen,teacher_cp,teacher_value FROM positions '
               'WHERE teacher_cp IS NOT NULL AND teacher_mate IS NULL AND teacher_value IS NOT NULL ORDER BY id')
        if limit: sql += ' LIMIT ' + str(int(limit))
        counts = Counter(); failures=[]; examples=[]
        for pid, fen, cp, value in db.execute(sql):
            fields = fen.split()
            if len(fields)<2 or fields[1] not in ('w', 'b'):
                failures.append((pid, 'invalid FEN turn'))
                continue
            side = fields[1];counts[side]+=1
            expected = math.tanh(float(cp)/400.0)
            white_cp = float(cp) if side=='w' else -float(cp)
            if not math.isfinite(float(value)) or abs(expected-float(value))>tolerance:
                failures.append((pid, 'teacher_value != tanh(teacher_cp/400)', float(cp),float(value),expected))
            if len(examples)<3 and side=='b':examples.append((pid,cp,white_cp,value))
        print('picoAlpha labeling contract: side-to-move, NOT white POV')
        print('checked=',sum(counts.values()),'white_to_move=',counts['w'],'black_to_move=',counts['b'])
        print('teacher_value/tanh(cp/400) mismatches=',len(failures))
        for x in failures[:12]: print('MISMATCH:',*x)
        for pid,cp,white_cp,value in examples:
            print(f'BLACK_TO_MOVE example id={pid} cp_stm={cp} cp_white={white_cp} value_stm={value}')
        if not counts['b']:print('WARNING: no black-to-move samples; cannot inspect black labels')
        if failures: return 1
        if not sum(counts.values()):print('WARNING: no labeled numeric positions found');return 2
        print('PASS: database labels internally consistent with STM teacher.py convention')
        print('NOTE: passing cannot certify how an external teacher labeled teacher_cp; check data provenance.')
        return 0
    finally:db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Read-only SQLite verification of picoAlpha cp/value perspective')
    p.add_argument('--db',required=True);p.add_argument('--limit',type=int,default=0)
    a=p.parse_args()
    if a.limit<0:p.error('--limit must be nonnegative')
    raise SystemExit(audit(a.db,a.limit))
