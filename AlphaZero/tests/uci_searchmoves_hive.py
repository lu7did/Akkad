#!/usr/bin/env python3
"""Integration test for AlphaZero/Hive UCI root restrictions.

Example (PowerShell):
 python AlphaZero/tests/uci_searchmoves_hive.py --exe AlphaZero/X86/build/AlphaZero.exe --weights AlphaZero/assets/network.pb.gz --cores 4
Requires the compiled patched engine and compatible neural weights.
"""
import argparse
import re
import subprocess
import sys
import threading
import time


def session(exe, weights, cores, fen, allowed, budget, extra):
    args = [exe, '--weights', weights, '--cores', str(cores), *extra]
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding='utf-8',
                         errors='replace', bufsize=1)
    lines = []
    stderr = []
    def consume(err):
        for line in p.stderr:
            err.append(line.rstrip())
    reader = threading.Thread(target=consume, args=(stderr,), daemon=True)
    reader.start()
    try:
        for command in ('uci', 'isready', 'position fen ' + fen,
                        'go depth 3 qdepth 2 movetime ' + str(budget) +
                        ' searchmoves ' + ' '.join(allowed)):
            p.stdin.write(command + '\n')
        p.stdin.flush()
        deadline = time.monotonic() + max(20., budget / 1000 + 20)
        # stdout.readline can wait indefinitely when a binary hangs; monitor
        # reading in a daemon thread and enforce an overall deadline.
        import queue
        messages = queue.Queue()
        def consume_out():
            for line in p.stdout:
                messages.put(line.strip())
        threading.Thread(target=consume_out, daemon=True).start()
        best = None
        while time.monotonic() < deadline:
            try:
                line = messages.get(timeout=.25)
            except queue.Empty:
                if p.poll() is not None:
                    break
                continue
            lines.append(line)
            if line.startswith('bestmove '):
                best = line.split()[1]
                break
        if best is None:
            raise AssertionError('missing bestmove; stderr: ' + ' | '.join(stderr[-8:]))
        if best not in allowed:
            raise AssertionError('illegal bestmove: ' + best + ' not in ' + str(allowed))
        reported = {}
        for line in lines:
            if not line.startswith('info ') or ' score cp ' not in line:
                continue
            m = re.search(r'\bscore cp (-?\d+)\b.*\bpv ([a-h][1-8][a-h][1-8][qrbn]?)\b', line)
            if m:
                reported[m.group(2)] = int(m.group(1))
        missing = set(allowed) - set(reported)
        if missing:
            raise AssertionError(f'missing scored PV for {sorted(missing)}; output: ' + repr(lines[-12:]))
        if any(m not in allowed for m in reported):
            raise AssertionError('unexpected root move in scored PV')
        print(f'PASS {"black" if " b " in fen else "white"}: bestmove={best} scores={reported}')
    finally:
        try:
            p.stdin.write('quit\n'); p.stdin.flush()
            p.wait(timeout=5)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            p.kill()
            p.wait(timeout=5)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--exe', required=True)
    a.add_argument('--weights', required=True)
    a.add_argument('--cores', type=int, default=1)
    a.add_argument('--movetime', type=int, default=1500)
    a.add_argument('--extra', nargs='*', default=[])
    opt = a.parse_args()
    initial = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'
    for fen, roots in ((initial + ' w KQkq - 0 1', ['e2e4']),
                       (initial + ' w KQkq - 0 1', ['e2e4', 'd2d4', 'g1f3']),
                       (initial + ' b KQkq - 0 1', ['e7e5', 'd7d5'])):
        session(opt.exe, opt.weights, opt.cores, fen, roots, opt.movetime, opt.extra)
    print('All AlphaZero/Hive searchmoves smoke tests passed')


if __name__ == '__main__':
    main()
