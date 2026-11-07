#!/usr/bin/env python3
"""Regression: half-closed TCP must still deliver UCI responses."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve()
SERVER = HERE.parents[2] / 'tools' / 'macos' / 'uci_tcp_server.py'

MOCK = '''#!/usr/bin/env python3
import sys, time
for line in sys.stdin:
    line = line.strip()
    if line == 'uci':
        print('id name mock', flush=True)
        print('option name Cores type spin default 2 min 1 max 16', flush=True)
        print('uciok', flush=True)
    elif line == 'isready': print('readyok', flush=True)
    elif line.startswith('go '):
        time.sleep(.12)
        print('info depth 2 nodes 19', flush=True)
        print('bestmove e2e4', flush=True)
    elif line == 'quit': break
'''


def port_available():
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def main():
    with tempfile.TemporaryDirectory() as tmp:
        engine = Path(tmp) / 'mock_engine'
        weights = Path(tmp) / 'weights.bin'
        engine.write_text(MOCK)
        engine.chmod(0o755)
        weights.write_bytes(b'weights')
        port = port_available()
        listener = subprocess.Popen([
            sys.executable, str(SERVER), '--host', '127.0.0.1', '--port', str(port),
            '--engine', str(engine), '--weights', str(weights), '--cores', '2',
            '--timeout', '2000'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 6
            while True:
                try:
                    client = socket.create_connection(('127.0.0.1', port), .2)
                    break
                except ConnectionRefusedError:
                    if time.monotonic() >= deadline:
                        raise AssertionError('listener did not start')
                    time.sleep(.05)
            with client:
                client.settimeout(6)
                client.sendall(b'uci\nisready\nposition startpos\ngo depth 2\n')
                client.shutdown(socket.SHUT_WR)
                chunks = []
                while True:
                    part = client.recv(4096)
                    if not part: break
                    chunks.append(part)
            reply = b''.join(chunks).decode('utf8')
            for token in ('uciok', 'readyok', 'info depth 2 nodes 19', 'bestmove e2e4'):
                assert token in reply, (token, reply)
            assert '🧠' not in reply and '🧮' not in reply
            print('PASS: half-close drains UCI responses; no emoji on TCP')
        finally:
            listener.terminate()
            try: listener.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                listener.kill()
                listener.communicate()

if __name__ == '__main__': main()
