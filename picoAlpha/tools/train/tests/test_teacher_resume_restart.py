"""Checkpoint/restart regression tests (no external chess binary required)."""
import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import connect, schema
from teacher import RestartableEngine, teach_positions

class EngineDied(Exception):
    pass

class Board:
    def __init__(self, fen):
        if '3+3' in fen:
            raise ValueError('invalid half-move clock')
        self.fen = fen
        self.turn = True
    def is_valid(self): return True
    def is_game_over(self, **kwargs): return False

class Score:
    def pov(self, turn): return self
    def is_mate(self): return False
    def score(self): return 70

class DummyEngine:
    def __init__(self, collector, fail_at=None, error=None):
        self.collector=collector
        self.fail_at=fail_at
        self.error=error
        self.closed=False
    def analyse(self, board, limit):
        self.collector.append(board.fen)
        if board.fen==self.fail_at:
            raise self.error or EngineDied('process died')
        return {'pv':[], 'score':Score()}
    def quit(self):
        self.closed=True
        raise EngineDied('dead loop')

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=connect(str(Path(self.temp.name)/'sample.pb'))
        self.addCleanup(self.db.close)
        schema(self.db)
        gid=self.db.execute("INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES('a',1,'{}','*','initial')").lastrowid
        for ply,fen in enumerate(['already','pending-2','bad 3+3','pending-4'],1):
            self.db.execute('INSERT INTO positions(game_id,ply,fen,played_uci) VALUES(?,?,?,?)',(gid,ply,fen,'e2e4'))
        self.db.execute("UPDATE positions SET teacher_at='2026-11-13 00:00:00',teacher_value=.5 WHERE fen='already'")
        self.db.commit()
        self.chess=type('Chess',(),{'Board':Board})

    def test_resume_skips_preserves_and_deletes_bad(self):
        calls=[]
        with contextlib.redirect_stdout(io.StringIO()):
            result=teach_positions(self.db,self.chess,DummyEngine(calls),lambda **k:k,10,resume=True,announce=lambda _:None)
        self.assertEqual(result,(2,1))
        self.assertEqual(calls,['pending-2','pending-4'])
        self.assertEqual(self.db.execute("SELECT teacher_value FROM positions WHERE fen='already'").fetchone()[0],.5)
        self.assertEqual(self.db.execute('SELECT count(*) FROM positions').fetchone()[0],3)
        self.assertEqual(self.db.execute('SELECT count(*) FROM positions WHERE teacher_at IS NOT NULL').fetchone()[0],3)
        calls2=[]
        with contextlib.redirect_stdout(io.StringIO()):
            result=teach_positions(self.db,self.chess,DummyEngine(calls2),lambda **k:k,10,resume=True,announce=lambda _:None)
        self.assertEqual(result,(0,0))
        self.assertFalse(calls2)

    def test_resume_handles_gaps_not_just_last_id(self):
        self.db.execute("UPDATE positions SET teacher_at='2026-11-13',teacher_value=.7 WHERE fen='pending-4'")
        self.db.commit()
        calls=[]
        with contextlib.redirect_stdout(io.StringIO()):
            teach_positions(self.db,self.chess,DummyEngine(calls),lambda **k:k,10,resume=True,announce=lambda _:None)
        self.assertEqual(calls,['pending-2'])
        self.assertEqual(self.db.execute("SELECT teacher_value FROM positions WHERE fen='pending-4'").fetchone()[0],.7)

    def test_automatic_restart_only_failed_position(self):
        calls=[]; attempts=[0]; emitted=[]; objects=[]
        def factory(command):
            attempts[0]+=1
            e=DummyEngine(calls, fail_at='pending-2' if attempts[0]==1 else None)
            objects.append(e)
            return e
        with RestartableEngine(factory, ['stockfish'],(EngineDied,),retries=2,delay=0,reporter=emitted.append) as engine:
            with contextlib.redirect_stdout(io.StringIO()):
                teach_positions(self.db,self.chess,engine,lambda **k:k,10,resume=True,announce=lambda _:None)
            self.assertEqual(engine.restarts,1)
        self.assertEqual(calls,['pending-2','pending-2','pending-4'])
        self.assertEqual(attempts[0],2)
        self.assertEqual(len(emitted),1)
        self.assertTrue(all(x.closed for x in objects))

    def test_persistent_death_has_bounded_retry_and_checkpoints(self):
        calls=[]; launches=[0]
        def factory(command):
            launches[0]+=1
            return DummyEngine(calls,fail_at='pending-2')
        with RestartableEngine(factory,['stockfish'],(EngineDied,),retries=2,delay=0,reporter=lambda _:None) as e:
            teach_positions(self.db,self.chess,e,lambda **k:k,10,resume=True,announce=lambda _:None)
        self.assertEqual(launches[0],4)
        self.assertEqual(self.db.execute("SELECT teacher_at FROM positions WHERE fen='pending-2'").fetchone()[0],None)
        self.assertEqual(self.db.execute('SELECT count(*) FROM teacher_quarantine').fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT teacher_value FROM positions WHERE fen='already'").fetchone()[0],.5)

    def test_startup_is_retried_and_quit_error_suppressed(self):
        attempts=[]
        def factory(command):
            attempts.append(1)
            if len(attempts)<2: raise EngineDied('startup failed')
            return DummyEngine([])
        with RestartableEngine(factory,['stockfish'],(EngineDied,),retries=2,delay=0,reporter=lambda _:None):
            pass
        self.assertEqual(len(attempts),2)

if __name__=='__main__': unittest.main()
