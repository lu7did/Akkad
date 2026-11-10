"""Portable smoke suite without TensorFlow: tests the shared UCI/search layer.

Run: python3 picoKeras/tests/test_multicore_smoke.py
Requires a C++17 compiler and pthread support. Does not test TensorFlow backends.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
FAKE = r'''
#include "model.hpp"
#include <algorithm>
#include <cmath>
struct Evaluator::Impl{int threads;};
Evaluator::Evaluator(const std::string&,size_t,int n):impl_(new Impl{n}){}
Evaluator::~Evaluator()=default;
void Evaluator::configure(const std::string&,const std::string&){}
double Evaluator::eval(const picoSargon::Board& b){double x=0;for(int i=0;i<64;i++){auto p=b.piece(i);x+=(p>0?1:-1)*std::abs(p)*0.002;}return std::clamp(x*b.turn,-1.,1.);}
std::vector<double> Evaluator::eval_batch(const std::vector<picoSargon::Board>& bs){std::vector<double> v;for(auto& b:bs)v.push_back(eval(b));return v;}
'''


def main():
    cxx = os.environ.get('CXX', 'c++')
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder)
        model = dest / 'mock.cpp'
        model.write_text(FAKE, encoding='utf-8')
        for enabled in (False, True):
            exe = dest / ('on' if enabled else 'off')
            args = [cxx, '-std=c++17', '-O2', '-pthread', '-I', str(SRC)]
            if enabled:
                args.append('-DPICOKERAS_MULTICORE=1')
            args += [str(SRC/'main.cpp'), str(SRC/'board.cpp'), str(model)]
            if enabled:
                args += [str(SRC/'multicore.cpp')]
            args += ['-o', str(exe)]
            subprocess.run(args, check=True, capture_output=True, text=True)
            cases = [(1, 1)] if not enabled else [(1, 1), (2, 2), (4, 2), (4, 3)]
            for cores, depth in cases:
                command = ['uci', 'isready', 'position startpos', 'go movetime 10000', 'quit']
                p = subprocess.run([str(exe), '--weights', 'mock', '--cores', str(cores),
                                    '--depth', str(depth)], input='\n'.join(command)+'\n',
                                   capture_output=True, text=True, timeout=20)
                assert p.returncode == 0, p.stderr
                assert 'uciok' in p.stdout and 'readyok' in p.stdout
                moves = re.findall(r'^bestmove (\S+)$', p.stdout, re.M)
                assert len(moves) == 1 and re.fullmatch(r'[a-h][1-8][a-h][1-8][qrbn]?', moves[0]), p.stdout
                actual = 1 if cores == 1 else depth
                assert f'depth {actual}' in p.stdout, p.stdout
                assert 'MULTICORE=' in p.stdout, p.stdout
            if not enabled:
                bad = subprocess.run([str(exe),'--weights','mock','--cores','2'],capture_output=True,text=True)
                assert bad.returncode != 0 and 'MULTICORE=ON' in bad.stderr
        print('PASS: UCI stdio, workers 1/2/4, depths 1/2/3, OFF rejects parallel mode')


if __name__ == '__main__':
    main()
