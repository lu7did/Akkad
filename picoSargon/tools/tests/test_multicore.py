#!/usr/bin/env python3
"""UCI regression: execute after compiling both OFF and ON binaries."""
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--serial', required=True)
parser.add_argument('--parallel', required=True)
parser.add_argument('--weights', required=True)
args = parser.parse_args()
positions = [
    'startpos',
    'fen r1bqkbnr/pppp1ppp/2n5/4p3/8/2N2N2/PPPPPPPP/R1BQKB1R w KQkq - 2 3',
]

def run(binary, position, cores=None, time=15000):
    command = [binary, args.weights]
    if cores is not None:
        command += ['--cores', str(cores)]
    proc = subprocess.run(command, input=f'uci\nisready\nposition {position}\ngo depth 4 movetime {time}\nquit\n',
                          text=True, capture_output=True, timeout=40, check=True)
    lines = proc.stdout.splitlines()
    assert 'uciok' in lines and 'readyok' in lines, lines
    info = next(line for line in lines if line.startswith('info ply '))
    move = next(line for line in lines if line.startswith('bestmove '))
    return info.split(' score cp ')[1].split()[0], move

for position in positions:
    expected = run(args.serial,position)
    assert expected == run(args.parallel,position,1), (position,expected,'cores=1')
    for cores in [2,3,256]:
        got = run(args.parallel,position,cores)
        assert got == expected, (position,cores,expected,got)
        print('PASS',position[:22],f'cores={cores}',got)
print('PASS: serial and parallel agree at depth 4')
