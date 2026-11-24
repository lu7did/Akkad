#!/usr/bin/env python3
"""Regression: bounded multi-root search, shared alpha and worker queue."""
import argparse
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--binary', required=True)
p.add_argument('--weights', required=True)
a = p.parse_args()

def run(cores, moves, depth=4):
    proc = subprocess.run([a.binary,'--weights',a.weights,'--cores',str(cores)],
        input='uci\nposition startpos\ngo depth {} qdepth 2 movetime 15000 searchmoves {}\nquit\n'.format(depth,' '.join(moves)),
        text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=40,check=True)
    lines = proc.stdout.splitlines()
    entries = [line for line in lines if re.match(r'^info depth {} multipv '.format(depth),line)]
    assert len(entries)==len(moves),(cores,moves,lines,proc.stderr)
    assert {re.search(r'\bpv (\S+)',line).group(1) for line in entries}==set(moves),entries
    for line in entries:
        assert 'core ' in line and 'string qdepth 2' in line,line
    best = next(line.split()[1] for line in lines if line.startswith('bestmove '))
    assert best in moves
    assert not any('upperbound' in line for line in entries if re.search(r'\bpv '+best+r'\b',line)),entries
    workers = [int(x) for x in re.findall(r'CORE_WORK core\[(\d+)\] depth='+str(depth)+r' moves=',proc.stderr)]
    if cores > 1:
        assert len(workers)==min(cores,len(moves)),(cores,workers,proc.stderr)
        counts = [int(x) for x in re.findall(r'CORE_WORK core\[\d+\] depth='+str(depth)+r' moves=(\d+)',proc.stderr)]
        assert sum(counts)==len(moves),(cores,counts,proc.stderr)
    return best,entries

for n in (1,2,4):
    b,e = run(n,['e2e4','d2d4','g1f3'])
    print('PASS cores',n,'best',b,'bounded',sum('upperbound' in x for x in e))
for n in (2,4):
    b,e=run(n,['e2e4'])
    print('PASS single root cores',n,'best',b)

for n in (2,4):
    b,e=run(n,['e2e4','d2d4','g1f3','c2c4','b1c3','g2g3','b2b3','f2f4','a2a3','h2h3'],5)
    assert e[0].split(' pv ')[1].split()[0] == b,(b,e[0])
    print('PASS queued roots',n,'best',b,'bounded',sum('upperbound' in x for x in e))
