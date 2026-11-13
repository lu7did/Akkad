"""Regression: invalid FEN is deleted while subsequent positions are labeled."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import connect, schema
from teacher import teach_positions

class MockBoard:
    def __init__(self, fen):
        if '3+3' in fen:
            raise ValueError('invalid half-move clock')
        self.turn = True
        self.fen = fen
    def is_valid(self):
        return self.fen != 'invalid-board'
    def is_game_over(self, **kw):
        return False

class Score:
    def pov(self, turn): return self
    def is_mate(self): return False
    def score(self): return 30

class Engine:
    def __init__(self): self.calls=[]
    def analyse(self, board, limit):
        self.calls.append(board.fen)
        return {'pv': [], 'score': Score()}

class InvalidFenTests(unittest.TestCase):
    def test_skip_bad_then_continue(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp)/'data.pb')
            with connect(path) as db:
                schema(db)
                gid=db.execute("INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES('a',1,'{}','*','initial')").lastrowid
                for ply,fen in enumerate(['good-1','rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 3+3 0 1','invalid-board','good-4'],1):
                    db.execute('INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(?,?,?,?)',(gid,ply,fen,'e2e4'))
                db.commit()
                engine=Engine(); logs=[]
                labeled, removed=teach_positions(db, type('Chess',(),{'Board':MockBoard}), engine,
                    lambda **kw:kw, 10, announce=logs.append)
                self.assertEqual((labeled,removed),(2,2))
                self.assertEqual(engine.calls,['good-1','good-4'])
                self.assertEqual(db.execute('SELECT count(*) FROM positions').fetchone()[0],2)
                self.assertTrue(all(r[0] is not None for r in db.execute('SELECT teacher_value FROM positions')))
                self.assertEqual(len([x for x in logs if 'Removed invalid position' in x]),2)

if __name__=='__main__': unittest.main()
