"""v0.1.15: impossible piece counts are excluded before UCI analysis."""
import contextlib
import io
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import connect, schema
from teacher import impossible_standard_material, teach_positions

class Chess:
    PAWN, KNIGHT, BISHOP, ROOK, QUEEN = 1,2,3,4,5
    WHITE, BLACK=True,False
    @staticmethod
    def Board(fen): return Board(fen)

class Board:
    def __init__(self,fen): self.fen=fen; self.turn=True
    def is_valid(self): return True
    def is_game_over(self, **kw): return False
    def pieces(self,piece,color):
        # Seven bishops with eight pawns; cannot arise in orthodox chess.
        if self.fen=='excess':
            n={Chess.PAWN:8,Chess.BISHOP:7,Chess.KNIGHT:0,Chess.ROOK:0,Chess.QUEEN:0}
        else:
            n={Chess.PAWN:8,Chess.BISHOP:2,Chess.KNIGHT:2,Chess.ROOK:2,Chess.QUEEN:1}
        return range(n[piece])

class Score:
    def pov(self,turn):return self
    def is_mate(self):return False
    def score(self):return 0
class Engine:
    def __init__(self):self.calls=[]
    def analyse(self,board,limit):
        self.calls.append(board.fen)
        return {'score':Score(),'pv':[]}

class Tests(unittest.TestCase):
    def test_impossible_material(self):
        self.assertTrue(impossible_standard_material(Board('excess'),Chess))
        self.assertFalse(impossible_standard_material(Board('normal'),Chess))
    def test_excess_bishops_never_reaches_stockfish(self):
        with tempfile.TemporaryDirectory() as td:
            db=connect(str(Path(td)/'positions.pb'))
            try:
                schema(db)
                gid=db.execute("INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES('a',1,'{}','*','initial')").lastrowid
                for i,fen in enumerate(('excess','normal'),1):
                    db.execute('INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(?,?,?,?)',(gid,i,fen,'e2e4'))
                db.commit()
                engine=Engine()
                with contextlib.redirect_stdout(io.StringIO()):
                    result=teach_positions(db,Chess,engine,lambda **kw:kw,10,resume=True,announce=lambda _:None)
                self.assertEqual(result,(1,1))
                self.assertEqual(engine.calls,['normal'])
            finally:db.close()

if __name__=='__main__':unittest.main()
