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
#* test_match_player_times_v06130.py
#* Regresión del tiempo de motores A/B en MATCH sin requerir python-chess.
#* v0.6.153
#=================================================================================================================*
"""Regresión del tiempo de motores A/B en MATCH sin requerir python-chess.

Ejecuta el main real extraído por AST con motores/partidas UCI simulados,
y un reloj controlado. No depende de sistemas externos ni ejecuta partidas reales.
"""
import argparse
import ast
import contextlib
import io
import json
import re
import sys
import time
import types
import unittest
from pathlib import Path

MATCH=Path(__file__).resolve().parents[1]/'src'/'sargon_nnue'/'sargon_match.py'

class FakeClock:
    def __init__(self): self.now=1000.0
    def monotonic(self): return self.now
    def time(self): return self.now

class FakeMove:
    def __init__(self,uci): self.value=uci
    def uci(self): return self.value
    @staticmethod
    def from_uci(s): return FakeMove(s)

class FakeBoard:
    def __init__(self): self.n=0;self.move_stack=[]
    @property
    def turn(self): return self.n%2==0
    def fen(self):return f'fake-fen:{self.n}'
    def ply(self):return self.n
    def push(self,m):self.n+=1;self.move_stack.append(m)
    def is_game_over(self,claim_draw=False):return self.n>=2
    def outcome(self,claim_draw=False):
        return types.SimpleNamespace(result=lambda:'1/2-1/2',termination=types.SimpleNamespace(name='DRAW_TEST'))


def exercise(*, failure=False):
    source=MATCH.read_text(encoding='utf-8')
    tree=ast.parse(source)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)
           and n.name in ('add_side','cmd_side','main')]
    assert len(nodes)==3
    clock=FakeClock()
    chess=types.SimpleNamespace(Board=FakeBoard,Move=FakeMove)
    chess.pgn=types.SimpleNamespace(Game=None)
    record=[]
    class FakeUCI:
        def __init__(self,cmd,log,label,heartbeat,identity=None,verbose=False):
            self.label=label;record.append(label)
        def send(self,command):pass
        def move(self,board,timeout):
            clock.now+=1.4 if self.label=='A' else 2.6
            if failure and self.label=='B': raise TimeoutError('test timeout')
            return FakeMove('e2e4' if board.turn else 'e7e5')
        def close(self):pass
    def get(brain,identity):
        assert brain=='brains-test.json'
        return {'player':'alphazero','evaluator':'lc0',
                'lc0-backend':'eigen' if identity=='alphie' else 'onnx-dml'}
    fake_time=types.SimpleNamespace(monotonic=clock.monotonic,time=clock.time)
    ns={'argparse':argparse,'sys':sys,'time':fake_time,'chess':chess,
        'Path':Path,'get':get,'ENGINE_KEYS':{'player','evaluator','lc0-backend'},
        'VERSION':'0.6.130','UCI':FakeUCI,'json':json}
    import csv
    ns['csv']=csv
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(MATCH),'exec'),ns)
    out=io.StringIO()
    with contextlib.redirect_stdout(out):
        exit_code=ns['main'](['--brain','brains-test.json','--idA','alphie','--idB','sophie','--pairs','1'])
    return exit_code,out.getvalue(),record

class MatchPlayerTimingTests(unittest.TestCase):
    def test_successful_both_colors_and_brain_names(self):
        status,output,engines=exercise()
        self.assertEqual(status,0)
        self.assertEqual(engines,['A','B'])
        lines=[ln for ln in output.splitlines() if '⌛A(' in ln]
        self.assertEqual(len(lines),2)
        for line in lines:
            self.assertIn('⌛A(1.4 secs) ⌛B(2.6 secs)',line)
            self.assertIn('(DRAW_TEST)',line)
        self.assertIn('⚪ (alphie)',lines[0])
        self.assertIn('⚫ (sophie)',lines[0])
        self.assertIn('⚪ (sophie)',lines[1])
        self.assertIn('⚫ (alphie)',lines[1])
        # La medición de espera por motor no incluye auditoría, inicio ni PGN.
        for line in lines:self.assertIn('⏱️    4.0s',line)

    def test_timeout_counts_waiting_time_and_marks_incomplete(self):
        status,output,engines=exercise(failure=True)
        self.assertEqual(status,2)
        lines=[ln for ln in output.splitlines() if '⌛A(' in ln]
        self.assertEqual(len(lines),2)
        self.assertIn('⌛A(1.4 secs) ⌛B(2.6 secs)',lines[0])
        self.assertIn('(ERROR:TimeoutError:test timeout)',lines[0])
        self.assertIn('⌛A(0.0 secs) ⌛B(2.6 secs)',lines[1])

    def test_version_and_no_csv_schema_modifications(self):
        source=MATCH.read_text(encoding='utf-8')
        self.assertIn("VERSION='0.6.130'",source)
        # Existing CSV contract remains identical to previous release.
        previous=(MATCH.parents[3]/'patch127'/'src'/'sargon_nnue'/'sargon_match.py')
        if previous.exists():
            old=previous.read_text(encoding='utf-8')
            marker="fieldnames=['game','pair','white','black'"
            self.assertEqual(old.split(marker,1)[1].split(')',1)[0],
                             source.split(marker,1)[1].split(')',1)[0])

if __name__=='__main__':unittest.main()
