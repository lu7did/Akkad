"""Regression tests for local UCI process transport; no real FICS server required."""
import importlib.util
import io
import queue
import sys
import textwrap
import types
from pathlib import Path
from contextlib import redirect_stderr
from unittest.mock import patch

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "fics_uci.py"

@pytest.fixture
def bridge_module():
    with patch.dict(sys.modules, {"chess": types.ModuleType("chess")}):
        spec = importlib.util.spec_from_file_location("bridge_test_uci_stdio", SOURCE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def make_engine(tmp_path, code):
    program = tmp_path / "engine with spaces.py"
    program.write_text(textwrap.dedent(code), encoding="utf-8")
    return program


def test_posix_arguments_preserve_spaces(bridge_module):
    assert bridge_module.parse_uci_args('--weights "/tmp/a b.tflite" --cores 4') == [
        '--weights', '/tmp/a b.tflite', '--cores', '4'
    ]


def test_uci_stdio_handshake_and_stderr(tmp_path, bridge_module):
    exe = make_engine(tmp_path, '''
        import sys
        args = sys.argv[1:]
        print('🧠 test telemetry ' + repr(args), file=sys.stderr, flush=True)
        for line in sys.stdin:
            op=line.strip().split(' ')[0]
            if op=='uci':
                print('id name Arbitrary Engine', flush=True)
                print('uciok', flush=True)
            elif op=='isready': print('readyok', flush=True)
            elif op=='go':
                print('info depth 2 nodes 55 time 30 score cp 15', flush=True)
                print('bestmove e2e4', flush=True)
            elif op=='quit': break
    ''')
    events = queue.Queue()
    err = io.StringIO()
    with redirect_stderr(err):
        link = bridge_module.ProcessUCILink('UCI', sys.executable, [str(exe), '--weights', 'abc def'], events)
        try:
            link.send('uci')
            assert events.get(timeout=3)[2].startswith('id name ')
            assert events.get(timeout=3)[2] == 'uciok'
            link.send('isready')
            assert events.get(timeout=3)[2] == 'readyok'
            link.send('position startpos')
            link.send('go movetime 500')
            assert events.get(timeout=3)[2].startswith('info depth 2')
            assert events.get(timeout=3)[2] == 'bestmove e2e4'
        finally:
            link.close()
    assert '🧠 test telemetry' in err.getvalue()
    assert "'abc def'" in err.getvalue()


def test_child_terminates_before_uciok(tmp_path, bridge_module):
    exe = make_engine(tmp_path, '''
        import sys
        print('Error initializing network', file=sys.stderr, flush=True)
        sys.exit(3)
    ''')
    events = queue.Queue()
    err = io.StringIO()
    with redirect_stderr(err):
        link = bridge_module.ProcessUCILink('UCI', sys.executable, [str(exe)], events)
        try:
            link.send('uci')
        except OSError:
            pass
        try:
            item = events.get(timeout=3)
            assert item[2].startswith(('__DISCONNECT__', '__ERROR__'))
        finally:
            link.close()
    assert 'Error initializing network' in err.getvalue()


def test_close_after_child_exit_and_pipe_break(tmp_path, bridge_module):
    exe = make_engine(tmp_path, 'import sys\nsys.exit(0)\n')
    events = queue.Queue()
    link = bridge_module.ProcessUCILink('UCI', sys.executable, [str(exe)], events)
    assert events.get(timeout=3)[2].startswith('__DISCONNECT__')
    assert link.send('isready') is False
    assert events.get(timeout=3)[2].startswith('__ERROR__')
    link.close()


def test_bad_args_are_rejected(bridge_module):
    with pytest.raises(ValueError):
        bridge_module.parse_uci_args(["--cores", "2"])
