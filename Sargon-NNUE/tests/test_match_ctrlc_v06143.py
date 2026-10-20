#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_match_ctrlc_v06143.py
#* Prueba de Ctrl+C/MATCH con UCI simulados: no necesita python-chess.
#* v0.6.153
#=================================================================================================================*
"""Prueba de Ctrl+C/MATCH con UCI simulados: no necesita python-chess."""
import argparse
import ast
import contextlib
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

SRC=Path(__file__).resolve().parents[1]/'src'/'sargon_nnue'/'sargon_match.py'

class Clock:
    def __init__(self):self.now=100.0
    def monotonic(self):return self.now
    def time(self):return self.now
class Move:
    def __init__(self,text):self.text=text
    def uci(self):return self.text
    @classmethod
    def from_uci(cls,text):return cls(text)
class Board:
    def __init__(self):self.n=0;self.move_stack=[]
    @property
    def turn(self):return self.n%2==0
    def fen(self):return f'fen-{self.n}'
    def ply(self):return self.n
    def push(self,m):self.n+=1;self.move_stack.append(m)
    def is_game_over(self,claim_draw=False):return self.n>=2
    def outcome(self,claim_draw=False):
        return types.SimpleNamespace(result=lambda:'1/2-1/2',termination=types.SimpleNamespace(name='DRAW_TEST'))
class PGN:
    def __init__(self):self.headers={};self.moves=[]
    def add_variation(self,m):self.moves.append(m);return self
    def __str__(self):return f'[Result "{self.headers.get("Result")}"]\n[Termination "{self.headers.get("Termination")}"]\n'

def exercise(interrupt_at=None, fail_init=None, pairs=1):
    clock=Clock(); calls=[]; closed=[]
    tree=ast.parse(SRC.read_text(encoding='utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('add_side','cmd_side','main')]
    class FakeUCI:
        def __init__(self,cmd,log,label,heartbeat,identity=None,verbose=False):
            if label==fail_init:raise KeyboardInterrupt
            self.label=label
        def send(self,line):pass
        def move(self,board,timeout):
            calls.append(self.label)
            clock.now+=2 if self.label=='A' else 3
            if len(calls)==interrupt_at:raise KeyboardInterrupt
            return Move('e2e4' if board.turn else 'e7e5')
        def close(self):closed.append(self.label)
    def get(file,identity):
        return {'player':'alphazero','evaluator':'zclassic','z-policy':'uniform'}
    chess=types.SimpleNamespace(Board=Board,Move=Move,pgn=types.SimpleNamespace(Game=PGN))
    ns={'argparse':argparse,'sys':sys,'time':types.SimpleNamespace(monotonic=clock.monotonic,time=clock.time),
        'chess':chess,'Path':Path,'get':get,
        'ENGINE_KEYS':{'player','evaluator','z-policy'},
        'VERSION':'0.6.143','UCI':FakeUCI,'json':json,'csv':csv}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(SRC),'exec'),ns)
    with tempfile.TemporaryDirectory() as d:
        report=Path(d)/'sample.csv';pgn=Path(d)/'sample.pgn'
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            code=ns['main'](['--brain','brains.json','--idA','beavys','--idB','butthead',
                             '--pairs',str(pairs),'--csv',str(report),'--pgn',str(pgn)])
        with report.open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
        return code,out.getvalue(),rows,pgn.read_text(encoding='utf8'),closed,calls

class MatchCtrlCTests(unittest.TestCase):
    def test_first_game_partial_saved_and_engines_closed(self):
        code,out,rows,pgn,closed,calls=exercise(interrupt_at=2,pairs=3)
        self.assertEqual(code,130)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['termination'],'INTERRUPTED_BY_USER')
        self.assertEqual(rows[0]['result'],'*')
        self.assertEqual(rows[0]['plies'],'1')
        self.assertIn('INTERRUPTED_BY_USER',pgn)
        self.assertIn('Games(1) Moves(1)',out)
        self.assertIn('⌛A(2) ⌛B(3)',out)
        self.assertEqual(set(closed),{'A','B'})
    def test_finished_game_remains_before_interruption(self):
        code,out,rows,pgn,closed,calls=exercise(interrupt_at=3,pairs=3)
        self.assertEqual(code,130)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['result'],'1/2-1/2')
        self.assertEqual(rows[1]['termination'],'INTERRUPTED_BY_USER')
        self.assertEqual(rows[1]['plies'],'0')
        self.assertIn('Games(2) Moves(2)',out)
        self.assertIn('⌛A(2) ⌛B(6)',out)
        self.assertEqual(set(closed),{'A','B'})
    def test_ctrl_c_during_second_engine_init_closes_first(self):
        code,out,rows,pgn,closed,calls=exercise(fail_init='B')
        self.assertEqual(code,130)
        self.assertIn('Games(0) Moves(0)',out)
        self.assertEqual(rows,[])
        self.assertEqual(closed,['A'])
    def test_normal_run_keeps_results_and_total(self):
        code,out,rows,pgn,closed,calls=exercise(pairs=1)
        self.assertEqual(code,0)
        self.assertEqual(len(rows),2)
        self.assertIn('Games(2) Moves(4)',out)
        self.assertEqual(set(closed),{'A','B'})
    def test_short_poll_for_windows_sigint(self):
        self.assertIn('wait = min(0.2, remaining',SRC.read_text(encoding='utf8'))
        self.assertIn('subprocess.CREATE_NEW_PROCESS_GROUP',SRC.read_text(encoding='utf8'))

if __name__=='__main__':unittest.main()
