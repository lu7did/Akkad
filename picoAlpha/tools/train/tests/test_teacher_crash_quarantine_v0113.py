"""Repeated Stockfish termination must not terminate a large training run."""
import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import connect, schema
from teacher import RestartableEngine, teach_positions

class Died(Exception): pass
class Board:
    def __init__(self, fen): self.fen=fen; self.turn=True
    def is_valid(self): return True
    def is_game_over(self, **k): return False
class Score:
    def pov(self, turn): return self
    def is_mate(self): return False
    def score(self): return 12
class E:
    def __init__(self, calls): self.calls=calls
    def analyse(self, board, limit):
        self.calls.append(board.fen)
        if board.fen.startswith('crash'): raise Died('exit code 1')
        return {'score':Score(),'pv':[]}
    def quit(self): pass
class Tests(unittest.TestCase):
    def db(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        db=connect(str(Path(tmp.name)/'test.pb')); self.addCleanup(db.close)
        schema(db)
        gid=db.execute("INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES('a',1,'{}','*','initial')").lastrowid
        for i,fen in enumerate(['done','crash-A','ok-1','crash-B','ok-2'],1):
            db.execute('INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(?,?,?,?)',(gid,i,fen,'e2e4'))
        db.execute("UPDATE positions SET teacher_at='2026-11-13',teacher_value=0.5 WHERE fen='done'")
        db.commit()
        return db
    def test_crashes_are_quarantined_and_later_positions_are_evaluated(self):
        db=self.db(); calls=[]; startups=[]; reports=[]
        def factory(cmd):
            startups.append(1)
            return E(calls)
        with RestartableEngine(factory,['stockfish'],(Died,),retries=1,delay=0,reporter=reports.append) as e:
            with contextlib.redirect_stdout(io.StringIO()):
                result=teach_positions(db,type('Chess',(),{'Board':Board}),e,lambda **k:k,10,resume=True,announce=reports.append)
        self.assertEqual(result,(2,0))
        self.assertEqual(db.execute('SELECT count(*) FROM positions').fetchone()[0],5)
        self.assertEqual(db.execute('SELECT count(*) FROM teacher_quarantine').fetchone()[0],2)
        self.assertEqual(db.execute('SELECT count(*) FROM positions WHERE teacher_at IS NOT NULL').fetchone()[0],3)
        self.assertEqual(calls,['crash-A','crash-A','ok-1','crash-B','crash-B','ok-2'])
        with RestartableEngine(factory,['stockfish'],(Died,),retries=1,delay=0,reporter=reports.append) as e:
            with contextlib.redirect_stdout(io.StringIO()):
                res=teach_positions(db,type('Chess',(),{'Board':Board}),e,lambda **k:k,10,resume=True,announce=reports.append)
        self.assertEqual(res,(0,0))
        self.assertEqual(len(calls),6)
    def test_nonresume_success_clears_old_quarantine(self):
        db=self.db()
        pid=db.execute("SELECT id FROM positions WHERE fen='ok-1'").fetchone()[0]
        db.execute("CREATE TABLE teacher_quarantine(position_id INTEGER PRIMARY KEY,fen TEXT,reason TEXT,attempts INTEGER,quarantined_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        db.execute("INSERT INTO teacher_quarantine(position_id,fen,reason,attempts) VALUES(?,?,?,?)",(pid,'ok-1','old error',4))
        db.commit()
        class Healthy:
            def analyse(self,board,limit): return {'score':Score(),'pv':[]}
        with contextlib.redirect_stdout(io.StringIO()):
            teach_positions(db,type('Chess',(),{'Board':Board}),Healthy(),lambda **k:k,10,resume=False,announce=lambda _:None)
        self.assertEqual(db.execute('SELECT count(*) FROM teacher_quarantine').fetchone()[0],0)
    def test_consecutive_failing_positions_trigger_healthy_control_and_continue(self):
        db=self.db()
        for i in range(3,6): db.execute('UPDATE positions SET fen=? WHERE ply=?',(f'crash-{i}',i))
        db.execute("INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(1,6,'crash-6','e2e4')")
        db.commit()
        calls=[]; reports=[]
        with RestartableEngine(lambda cmd:E(calls),['sf'],(Died,),retries=0,delay=0,reporter=lambda _:None) as e:
            with contextlib.redirect_stdout(io.StringIO()):
                result=teach_positions(db,type('Chess',(),{'Board':Board}),e,lambda **k:k,10,resume=True,announce=reports.append)
        self.assertEqual(result,(0,0))
        self.assertEqual(db.execute('SELECT count(*) FROM teacher_quarantine').fetchone()[0],5)
        self.assertTrue(any('control OK' in r for r in reports))
        self.assertIn('rnbqkbnr/pppppppp', ''.join(calls))

    def test_consecutive_failure_stops_if_control_fails(self):
        db=self.db()
        for i in range(2,6): db.execute('UPDATE positions SET fen=? WHERE ply=?',(f'crash-{i}',i))
        db.execute("INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(1,6,'crash-6','e2e4')")
        db.commit()
        class Broken(E):
            def analyse(self,board,limit): raise Died('broken globally')
        with RestartableEngine(lambda cmd:Broken([]),['sf'],(Died,),retries=0,delay=0,reporter=lambda _:None) as e:
            with self.assertRaisesRegex(RuntimeError,'orthodox starting-position control'):
                with contextlib.redirect_stdout(io.StringIO()):
                    teach_positions(db,type('Chess',(),{'Board':Board}),e,lambda **k:k,10,resume=True,announce=lambda _:None)

if __name__=='__main__': unittest.main()
