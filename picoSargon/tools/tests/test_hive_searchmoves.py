#!/usr/bin/env python3
"""Tests Hive/UCI root filtering and per-move telemetry (stdlib only).

Usage: python picoSargon/tools/tests/test_hive_searchmoves.py \
  --binary <compiled picoSargon> --weights <grumpy.bin> [--cores 2]
"""
import argparse
import re
import subprocess


def run(binary, weights, commands, cores=None):
    args = [binary, '--weights', weights]
    if cores is not None:
        args.extend(['--cores', str(cores)])
    completed = subprocess.run(args, input='\n'.join(commands + ['quit', '']),
                               text=True, capture_output=True, timeout=60, check=True)
    return completed.stdout.splitlines(), completed.stderr


def assert_batch(binary, weights, cores):
    data, _ = run(binary, weights, ['uci', 'isready', 'position startpos',
      'go depth 4 qdepth 9 movetime 15000 searchmoves e2e4 d2d4 g1f3'], cores)
    assert 'uciok' in data and 'readyok' in data, data
    rows = [line for line in data if re.match(r'^info depth 4 multipv \d+ ', line)]
    assert len(rows) == 3, data
    moves = {re.search(r'\bpv ([a-h][1-8][a-h][1-8][qrbn]?)\b', row).group(1) for row in rows}
    assert moves == {'e2e4', 'd2d4', 'g1f3'}, rows
    for row in rows:
        for field in ['score cp ', 'nodes ', 'time ', 'nps ', 'string qdepth 9', 'qnodes ', 'root ']:
            assert field in row, row
    best = next(line.partition(' ')[2] for line in data if line.startswith('bestmove '))
    assert best in moves, (best, moves)
    indices = [int(re.search(r'\bmultipv (\d+)', row).group(1)) for row in rows]
    scores = [int(re.search(r'\bscore cp (-?\d+)', row).group(1)) for row in rows]
    assert indices == [1, 2, 3] and scores == sorted(scores, reverse=True), rows
    print(f'PASS: restricted multipv cores={cores}; best={best}; scores={scores}')


def assert_errors_and_recovery(binary, weights, cores):
    data, _ = run(binary, weights, ['position startpos',
      'go depth 3 searchmoves e2e5', 'isready',
      'go depth 2 movetime 15000 searchmoves e2e4'], cores)
    assert any(line.startswith('info string ERROR go: illegal move:') for line in data), data
    assert 'bestmove 0000' in data and 'readyok' in data, data
    assert 'bestmove e2e4' in data, data
    print(f'PASS: invalid root fails safely cores={cores}')


def assert_unrestricted(binary, weights, cores):
    data, _ = run(binary, weights, ['position startpos', 'go depth 2 movetime 15000'], cores)
    assert sum(line.startswith('bestmove ') for line in data) == 1, data
    assert not any(' multipv ' in line for line in data), data
    print(f'PASS: ordinary UCI preserved cores={cores}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', required=True)
    p.add_argument('--weights', required=True)
    p.add_argument('--cores', type=int)
    a = p.parse_args()
    assert_batch(a.binary, a.weights, a.cores)
    assert_errors_and_recovery(a.binary, a.weights, a.cores)
    assert_unrestricted(a.binary, a.weights, a.cores)


if __name__ == '__main__':
    main()
