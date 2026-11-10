"""Subprocess UCI stderr must preserve Unicode independently of UCI stdout."""
import io
import sys
import textwrap
from contextlib import redirect_stderr
from challenger.uci_client import ProcessUCIClient


def test_utf8_stderr_is_transparent_and_does_not_pollute_uci(tmp_path):
    engine = tmp_path / 'engine.py'
    engine.write_text(textwrap.dedent('''
        import sys
        sys.stderr.buffer.write('🧠 AlphaZero core[0] stop=completed\\n'.encode('utf-8'))
        sys.stderr.flush()
        for cmd in sys.stdin:
            cmd = cmd.strip()
            if cmd == 'uci':
                print('id name Example engine', flush=True)
                print('uciok', flush=True)
            elif cmd == 'isready': print('readyok', flush=True)
            elif cmd.startswith('go '):
                print('info depth 2 nodes 1201', flush=True)
                print('bestmove e2e4', flush=True)
            elif cmd == 'quit': break
    '''), encoding='utf-8')
    log = io.StringIO()
    with redirect_stderr(log):
        cli = ProcessUCIClient(sys.executable, ['-u', str(engine)], timeout_ms=3000)
        try:
            cli.connect()
            assert cli.id_name == 'Example engine'
            assert cli.go(1000, 1000).move == 'e2e4'
        finally:
            cli.close()
    assert log.getvalue() == '🧠 AlphaZero core[0] stop=completed\n'
