"""Regression: cutoff at an incomplete level preserves the last full depth."""
import re
import subprocess
import tempfile
from pathlib import Path
from test_multicore_smoke import SRC, FAKE


def main():
    mock = FAKE.replace('#include <cmath>', '#include <cmath>\n#include <thread>\n#include <chrono>')
    mock = mock.replace('std::vector<double> Evaluator::eval_batch(const std::vector<picoSargon::Board>& bs){',
                        'std::vector<double> Evaluator::eval_batch(const std::vector<picoSargon::Board>& bs){std::this_thread::sleep_for(std::chrono::milliseconds(20));')
    mock = mock.replace('double Evaluator::eval(const picoSargon::Board& b){',
                        'double Evaluator::eval(const picoSargon::Board& b){')
    with tempfile.TemporaryDirectory() as td:
        path = Path(td)
        (path / 'model.cpp').write_text(mock)
        exe = path / 'picoKeras_test'
        subprocess.run(['c++','-std=c++17','-O2','-pthread','-DPICOKERAS_MULTICORE=1',
                        '-I',str(SRC),str(SRC/'main.cpp'),str(SRC/'board.cpp'),
                        str(SRC/'multicore.cpp'),str(path/'model.cpp'),'-o',str(exe)],
                       check=True, capture_output=True, text=True)
        def ask(cores, depth, budget):
            inp='uci\nisready\nposition startpos\ngo movetime '+str(budget)+'\nquit\n'
            p=subprocess.run([str(exe),'--weights','mock','--cores',str(cores),
                              '--depth',str(depth),'--tmax','1000'],input=inp,
                             capture_output=True,text=True,timeout=20)
            assert p.returncode==0,p.stderr
            return p.stdout
        baseline=ask(1,1,1000)
        partial=ask(2,3,80)
        full=ask(2,2,1000)
        move=lambda x:re.search(r'^bestmove (\S+)$',x,re.M).group(1)
        depth=lambda x:int(re.search(r'^info ply \d+ depth (\d+)',x,re.M).group(1))
        assert depth(partial)==1,(partial,full)
        assert 'status=partial' in partial and 'fallback=false' in partial,partial
        assert move(partial)==move(baseline),(partial,baseline)
        assert depth(full)==2,full
        assert 'requested_depth=3' in partial and 'level_ms=[' in partial
        print('PASS: depth-1 result retained on interrupted depth-2/3, true depth/score, depth-2 completed')

if __name__=='__main__':main()
