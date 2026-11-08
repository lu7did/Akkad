#!/usr/bin/env python3
"""AlphaZero native UCI smoke test v0.2.9 (no network/TCP listener)."""
import argparse
import os
import queue
import re
import subprocess
import sys
import threading
import time


def main():
    ap = argparse.ArgumentParser(description="UCI smoke: verify stdin/stdout and stderr telemetry")
    ap.add_argument('--engine', required=True)
    ap.add_argument('--weights', required=True)
    ap.add_argument('--backend', default='eigen')
    ap.add_argument('--backend-options', default='')
    ap.add_argument('--cores', type=int, default=1)
    ap.add_argument('--nodes', type=int, default=8)
    ap.add_argument('--timeout', type=int, default=30000)
    args = ap.parse_args()
    for path in (args.engine, args.weights):
        if not os.path.isfile(path):
            ap.error('file not found: ' + path)
    if args.cores < 1 or args.nodes < 1 or args.timeout < 1:
        ap.error('cores, nodes and timeout must be positive')
    cmd = [args.engine, '--weights', args.weights, '--backend', args.backend,
           '--backend-options', args.backend_options, '--cores', str(args.cores)]
    print('⚙️ Engine:', args.engine, 'Weights:', args.weights, flush=True)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, encoding='utf-8', errors='replace', bufsize=1)
    q = queue.Queue()
    def consume(stream, is_uci):
        try:
            for raw in stream:
                line = raw.rstrip('\r\n')
                if is_uci:
                    q.put(line)
                    if line.startswith(('⬅️', '➡️', '⚙️', '🧠', '📊')):
                        q.put(('INVALID', line))
                else:
                    print(line, file=sys.stderr, flush=True)
        finally:
            if is_uci:
                q.put(None)
    for stream, is_uci in ((p.stdout, True), (p.stderr, False)):
        threading.Thread(target=consume, args=(stream, is_uci), daemon=True).start()
    def send(line):
        p.stdin.write(line + '\n')
        p.stdin.flush()
    def expect(label, predicate, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                item = q.get(timeout=min(0.5, max(0.001, end - time.monotonic())))
            except queue.Empty:
                continue
            if isinstance(item, tuple):
                raise RuntimeError('decorated stdout UCI: ' + repr(item[1]))
            if item is None:
                raise RuntimeError('engine stdout closed while awaiting ' + label)
            print('➡️ UCI', item, flush=True)
            if item.startswith('info string ERROR'):
                raise RuntimeError(item)
            if predicate(item):
                return
        raise TimeoutError(label)
    try:
        send('uci')
        expect('uciok', lambda s: s == 'uciok', 90)
        send('isready')
        expect('readyok', lambda s: s == 'readyok', 180)
        send('ucinewgame')
        send('position startpos')
        send(f'go nodes {args.nodes} movetime {args.timeout}')
        expect('bestmove', lambda s: s.startswith('bestmove ') and s.split()[1] not in ('0000','(none)'),
               max(45, args.timeout / 1000 + 30))
        print('SMOKE PASS: UCI input/output and bestmove', flush=True)
        return 0
    except Exception as e:
        print('SMOKE FAIL:', e, file=sys.stderr)
        return 1
    finally:
        if p.poll() is None:
            try:
                send('quit')
                p.wait(timeout=4)
            except (OSError, subprocess.TimeoutExpired):
                p.kill()
                p.wait()

if __name__ == '__main__':
    sys.exit(main())
