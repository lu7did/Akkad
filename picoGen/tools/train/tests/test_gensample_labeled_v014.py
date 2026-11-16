"""Regression: the sampling denominator is completed Stockfish labels only."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from genSample import sample_database
from gen_common import CREATE_SQL


def make_mixed_database(path):
    with sqlite3.connect(path) as db:
        db.executescript(CREATE_SQL)
        db.execute('''INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen)
                      VALUES('test.pgn',1,'{}','1-0','start')''')
        # 5 completed; 4 without evaluation or with partial metadata.
        for i in range(9):
            labeled = i < 5
            cp = 0 if i == 0 else (i * 10 if i != 5 else 90)
            value = (0.0 if i == 0 else i / 100.0) if labeled else None
            at = '2026-11-14 00:00:00' if labeled or i == 6 else None
            db.execute('''INSERT INTO positions(game_id,ply,fen,played_uci,teacher_uci,
                            teacher_cp,teacher_mate,teacher_value,teacher_at)
                            VALUES(1,?,?,?,?,?,?,?,?)''',
                       (i + 1, f'fen_{i}', 'e2e4', 'e2e4' if labeled else None,
                        cp, None, value, at))


def check_output(dbpath, expected):
    with sqlite3.connect(dbpath) as db:
        assert db.execute('SELECT COUNT(*) FROM positions').fetchone()[0] == expected
        assert db.execute('''SELECT COUNT(*) FROM positions
                             WHERE teacher_value IS NULL OR teacher_at IS NULL''').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM positions WHERE teacher_value=0').fetchone()[0] <= 1
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_pct_100_counts_only_completed(tmp_path):
    src, dst = tmp_path/'source.pb', tmp_path/'sample.pb'
    make_mixed_database(src)
    assert sample_database(src, dst, pct=100) == 5
    check_output(dst, 5)


def test_pct_40_uses_labeled_denominator(tmp_path):
    src, dst = tmp_path/'source.pb', tmp_path/'sample.pb'
    make_mixed_database(src)
    assert sample_database(src, dst, pct=40) == 2
    check_output(dst, 2)


def test_sample_cap_and_precedence(tmp_path):
    src, dst = tmp_path/'source.pb', tmp_path/'sample.pb'
    make_mixed_database(src)
    assert sample_database(src, dst, sample=99, pct=0) == 5
    check_output(dst, 5)
    assert sample_database(src, dst, sample=1, pct=100) == 1
    check_output(dst, 1)


def test_zero_eligible(tmp_path):
    src, dst = tmp_path/'source.pb', tmp_path/'sample.pb'
    make_mixed_database(src)
    with sqlite3.connect(src) as db:
        db.execute('UPDATE positions SET teacher_value=NULL')
    assert sample_database(src, dst, pct=100) == 0
    check_output(dst, 0)
