"""Regression: malformed Stockfish payload is discarded and does not poison checkpoints."""
import contextlib
import io
import math
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import connect, schema
from teacher import BadEngineResult, interpret_analysis, teach_positions

class B:
    def __init__(self, fen):
        self.fen = fen
        self.turn = True
        self.legal_moves = []
    def is_valid(self): return True
    def is_game_over(self, **kwargs): return False

class S:
    def __init__(self, score): self.cp = score
    def pov(self, _): return self
    def is_mate(self): return False
    def score(self): return self.cp

class Engine:
    def __init__(self): self.seen=[]
    def analyse(self, board, limit):
        self.seen.append(board.fen)
        if board.fen == 'invalid-engine': return {'score':S(float('nan'))}
        if board.fen == 'empty-engine': return {}
        return {'score':S(40)}

class Tests(unittest.TestCase):
    def test_invalid_responses(self):
        for info in [{}, None, {'score':S(None)}, {'score':S(float('nan'))}, {'score':S(float('inf'))}]:
            with self.subTest(info=info):
                with self.assertRaises(BadEngineResult):
                    interpret_analysis(info, B('a'))
    def test_invalid_data_deleted_and_resume_skips_earlier_labels(self):
        with tempfile.TemporaryDirectory() as td:
            db=connect(str(Path(td)/'test.pb'))
            try:
                schema(db)
                gid=db.execute("INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES('a',1,'{}','*','x')").lastrowid
                for ix,fen in enumerate(('done','invalid-engine','empty-engine','good'),1):
                    db.execute('INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(?,?,?,?)',(gid,ix,fen,'e2e4'))
                db.execute("UPDATE positions SET teacher_at='2026-11-13',teacher_value=0.12 WHERE fen='done'")
                db.commit()
                e=Engine()
                with contextlib.redirect_stdout(io.StringIO()):
                    result=teach_positions(db,type('Chess',(),{'Board':B}),e,lambda **k:k,10,resume=True,announce=lambda x:None)
                self.assertEqual(result,(1,2))
                self.assertEqual(e.seen,['invalid-engine','empty-engine','good'])
                self.assertEqual(db.execute('SELECT count(*) FROM positions').fetchone()[0],2)
                self.assertEqual(db.execute("SELECT teacher_value FROM positions WHERE fen='done'").fetchone()[0],.12)
                self.assertIsNotNone(db.execute("SELECT teacher_at FROM positions WHERE fen='good'").fetchone()[0])
            finally: db.close()
if __name__ == '__main__': unittest.main()
