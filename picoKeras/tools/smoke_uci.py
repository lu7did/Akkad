#!/usr/bin/env python3
"""picoKeras UCI subprocess test, using BOM-free bytes on Windows and POSIX."""
import argparse
import os
import pathlib
import queue
import subprocess
import sys
import threading
import time

def test(executable, model, timeout):
    p = subprocess.Popen([str(executable), '--weights', str(model)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         bufsize=0)
    q = queue.Queue()
    def reader(stream, kind):
        for line in iter(stream.readline, b''):
            q.put((kind, line.decode('utf-8', 'replace').rstrip()))
        q.put((kind, None))
    for stream, kind in ((p.stdout, 'UCI'), (p.stderr, 'ERR')):
        threading.Thread(target=reader, args=(stream, kind), daemon=True).start()
    def expect(command, expected):
        p.stdin.write((command + '\n').encode('ascii'))
        p.stdin.flush()
        print('>>>', command, flush=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                kind, line = q.get(timeout=min(0.3, max(0.01, deadline-time.monotonic())))
            except queue.Empty:
                if p.poll() is not None:
                    raise RuntimeError(f'Engine exited {p.returncode} before {expected}')
                continue
            if line is None:
                continue
            print(kind, line, flush=True)
            if kind == 'UCI' and (line == expected or line.startswith(expected + ' ')):
                return
        raise TimeoutError(f'Timed out waiting for {expected} ({timeout}s)')
    try:
        expect('uci', 'uciok')
        expect('isready', 'readyok')
        p.stdin.write(b'position startpos\n'); p.stdin.flush()
        expect('go movetime 1000', 'bestmove')
        p.stdin.write(b'quit\n');p.stdin.flush()
        p.wait(timeout=10)
        if p.returncode:
            raise RuntimeError(f'Engine exit code: {p.returncode}')
        print('UCI SMOKE OK')
    finally:
        if p.poll() is None:
            p.kill();p.wait()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--engine', required=True)
    ap.add_argument('--weights', required=True)
    ap.add_argument('--timeout', type=float, default=90)
    a=ap.parse_args()
    test(a.engine, a.weights, a.timeout)
if __name__ == '__main__':
    main()
