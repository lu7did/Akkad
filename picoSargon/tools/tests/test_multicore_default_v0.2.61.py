#!/usr/bin/env python3
"""Verify compiled MULTICORE remains available but runtime default is one core."""
import argparse
import re
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument('--binary', required=True)
ap.add_argument('--weights', required=True)
a = ap.parse_args()

def run(extra, commands):
    p = subprocess.run([a.binary, '--weights', a.weights] + extra,
        input='uci\nisready\nposition startpos\n' + commands + '\nquit\n',
        text=True, encoding='utf-8', errors='replace', capture_output=True,
        timeout=60, check=True)
    return p.stdout, p.stderr

out, err = run([], 'go depth 3 movetime 10000 searchmoves e2e4 d2d4 g1f3')
assert 'option name Cores type spin default 1 min 1 max 1024' in out, out
assert 'bestmove ' in out, out
assert not re.search(r'CORE_WORK core\[1\]', err), err
print('PASS default cores=1')
out, err = run(['--cores', '2'], 'go depth 3 movetime 10000 searchmoves e2e4 d2d4 g1f3')
assert 'bestmove ' in out, out
assert 'CORE_WORK core[1]' in err, err
print('PASS explicit cores=2')
out, err = run([], 'setoption name Cores value 2\ngo depth 3 movetime 10000 searchmoves e2e4 d2d4 g1f3')
assert 'bestmove ' in out, out
assert 'CORE_WORK core[1]' in err, err
print('PASS UCI setoption Cores=2')
