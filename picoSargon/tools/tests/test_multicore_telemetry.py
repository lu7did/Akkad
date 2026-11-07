#!/usr/bin/env python3
"""Smoke test: timestamped per-core rows, barrier, stop, and UCI isolation."""
import argparse
import re
import subprocess

p=argparse.ArgumentParser()
p.add_argument('--engine',required=True)
p.add_argument('--weights',required=True)
a=p.parse_args()
pattern=re.compile(r'^\[\d\d:\d\d:\d\d\] 🧮 core\[(\d+)\] level=(\d+) status=(completed|stopped)\s+nodes=(\d+) qnodes=(\d+) elapsed=(\d+) msec$')
for ms in (15000,2):
 result=subprocess.run([a.engine,'--weights',a.weights,'--cores','3'],
  input=f'uci\nposition startpos\ngo depth {5 if ms>100 else 16} movetime {ms}\nquit\n',
  text=True,capture_output=True,timeout=60,check=True)
 rows=[line for line in result.stderr.splitlines() if '🧮' in line]
 assert rows, result.stderr
 for line in rows:
  assert pattern.fullmatch(line),line
 assert 'uciok' in result.stdout and 'bestmove ' in result.stdout,result.stdout
 assert '🧮' not in result.stdout
 if ms>100:
  from collections import Counter
  counts=Counter(int(pattern.fullmatch(line).group(2)) for line in rows)
  assert all(n==3 for n in counts.values()),counts
 print('PASS telemetry', 'normal' if ms>100 else 'deadline',len(rows),'rows')
