#!/usr/bin/env python3
"""UCI stdout must contain no human telemetry; stderr core order precedes info."""
import argparse
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--engine', required=True)
parser.add_argument('--weights', required=True)
parser.add_argument('--cores', type=int, default=2)
args = parser.parse_args()
commands = 'uci\nisready\nposition startpos\ngo depth 3\nquit\n'
proc = subprocess.run([args.engine, '--weights', args.weights, '--cores', str(args.cores), '--timeout', '30000'],
                      input=commands, capture_output=True, text=True, timeout=90)
assert proc.returncode == 0, proc.stderr
stdout = proc.stdout.splitlines()
stderr = proc.stderr.splitlines()
assert 'uciok' in stdout and 'readyok' in stdout
assert any(line.startswith('info ') for line in stdout)
assert any(line.startswith('bestmove ') for line in stdout)
assert all(not any(ord(c)>127 for c in line) for line in stdout), 'non-ASCII UCI stdout'
assert all(not re.match(r'^\[?\d\d:\d\d:',line) for line in stdout), 'timestamp in UCI stdout'
core = [i for i,line in enumerate(stderr) if '🧮 core[' in line]
info = [i for i,line in enumerate(stderr) if '🧠 info ' in line]
best = [i for i,line in enumerate(stderr) if '🧠 bestmove ' in line]
assert info and best, stderr
assert (not core or max(core)<info[-1]) and info[-1]<best[-1], stderr
assert all(re.match(r'^\[\d{2}:\d{2}:\d{2}\]',stderr[i]) for i in core+info+best)
print('PASS: UCI stdout clean, stderr diagnostic ordered')
