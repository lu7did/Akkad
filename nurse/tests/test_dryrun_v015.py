"""Regresiones del wrapper TCP real de nurse_dryrun."""
import contextlib
import importlib.util
import io
import json
import socket
import threading
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'nurse_dryrun.py'
spec = importlib.util.spec_from_file_location('nurse_dryrun', SCRIPT)
dryrun = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dryrun)


class MockUCI:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(('127.0.0.1', 0))
        self.server.listen()
        self.port = self.server.getsockname()[1]
        self.lines = []
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        sock, _ = self.server.accept()
        with sock:
            with sock.makefile('r', encoding='utf-8') as reader, sock.makefile('w', encoding='utf-8') as writer:
                for line in reader:
                    line=line.strip();self.lines.append(line)
                    if line=='uci':
                        writer.write('id name Motor Remoto Arbitrario\nuciok\n')
                    elif line=='isready':
                        writer.write('readyok\n')
                    elif line.startswith('go '):
                        writer.write('info depth 2 nodes 123 time 42 score cp 17\n')
                        writer.write('bestmove c3c6\n')
                    elif line=='quit':
                        break
                    writer.flush()
        self.server.close()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class TestDryrun(unittest.TestCase):
    def test_success_through_tcp_listener(self):
        mock=MockUCI()
        with tempfile.TemporaryDirectory() as d:
            conf=Path(d)/'brains.json'
            conf.write_text(json.dumps({'brains': {'myremote': {'type':'external',
                'url':f'127.0.0.1:{mock.port}', 'tmax':250, 'timeout':1000}}}), encoding='utf-8')
            stdout=io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code=dryrun.main(['--brains',str(conf),'--id','myremote','--port',str(free_port()),'--seed','2'])
            report=stdout.getvalue()
            self.assertEqual(code,0,report)
            self.assertIn('Motor Remoto Arbitrario',report)
            self.assertIn('✅',report)
            self.assertIn('move=c3c6',report)
            self.assertTrue(any(x.startswith('position fen ') for x in mock.lines))
            self.assertIn('go movetime 250',mock.lines)
            self.assertIn('uci',mock.lines)
            self.assertIn('isready',mock.lines)

    def test_duplicate_keys_rejected_before_binding(self):
        with tempfile.TemporaryDirectory() as d:
            conf=Path(d)/'brains.json'
            conf.write_text('{"brains":{"dup":{"type":"external"},"dup":{"type":"external"}}}',encoding='utf-8')
            err=io.StringIO()
            with contextlib.redirect_stderr(err):
                code=dryrun.main(['--brains',str(conf),'--id','dup','--port',str(free_port())])
            self.assertEqual(code,2)
            self.assertIn('duplicada',err.getvalue())

    def test_unknown_brain_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            conf=Path(d)/'brains.json'
            conf.write_text('{"brains":{}}',encoding='utf-8')
            err=io.StringIO()
            with contextlib.redirect_stderr(err):
                code=dryrun.main(['--brains',str(conf),'--id','absent','--port',str(free_port())])
            self.assertEqual(code,2)
            self.assertIn('desconocido',err.getvalue())


if __name__=='__main__':unittest.main()
