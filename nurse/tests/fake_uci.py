"""Controlled UCI child used for integration testing without python-chess."""
import sys,time
print('Fake UCI started',file=sys.stderr,flush=True)
for incoming in sys.stdin:
    line=incoming.strip()
    if line=='uci':
        print('id name Nurse Fake Engine')
        print('uciok',flush=True)
    elif line=='isready':print('readyok',flush=True)
    elif line.startswith('go '):
        print('info depth 2 score cp 42 nodes 123 time 15 nps 8200',flush=True)
        print('bestmove e2e4',flush=True)
    elif line=='quit':break
