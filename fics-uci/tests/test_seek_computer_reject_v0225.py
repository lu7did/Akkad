"""Regression: a FICS computer restriction suspends outbound 'play' attempts.

These tests extract the real Bridge.seek_response method from the source AST so
no server, credentials, chess package, or network connection is needed.
"""
from pathlib import Path
import ast
import types

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'fics_uci.py'

def method_from_source():
    module = ast.parse(SOURCE.read_text(encoding='utf-8'))
    bridge = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'Bridge')
    method = next(n for n in bridge.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'seek_response')
    node = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(node)
    logs = []
    namespace = {'log': lambda *args: logs.append(args)}
    exec(compile(node, str(SOURCE), 'exec'), namespace)
    return namespace['seek_response'], logs

class FakeBridge:
    def __init__(self):
        self.seek_pending = 27
        self.seek_suspended = False
        self.released = []
        self.choices = []
    def release_seek(self, reason, cooldown=True):
        self.released.append((reason, cooldown))
        self.seek_pending = None
    def choose_seek(self):
        # The real choose_seek() checks seek_suspended before emitting play.
        if not self.seek_suspended:
            self.choices.append('attempt-next-play')

def test_computer_rejection_suspends_session():
    callback, logs = method_from_source()
    b = FakeBridge()
    assert callback(b, 'Computers may not use this command.') is True
    assert b.seek_suspended is True
    assert b.seek_pending is None
    assert b.choices == []
    assert len(b.released) == 1
    assert any('no puede aceptar' in str(item) for item in logs)

def test_normal_seek_errors_do_not_suspend_all_seeks():
    callback, _ = method_from_source()
    b = FakeBridge()
    assert callback(b, 'No longer available') is True
    assert b.seek_suspended is False
    assert b.choices == ['attempt-next-play']

def test_unrelated_server_line_is_ignored():
    callback, _ = method_from_source()
    b = FakeBridge()
    assert callback(b, 'Horsian accepts your challenge') is False
    assert b.seek_pending == 27
    assert b.released == []
