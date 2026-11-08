#!/usr/bin/env python3
"""UCI test for a compiled AlphaZero. Needs weights and a platform executable."""
import argparse
import subprocess
import sys

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--engine',required=True)
    p.add_argument('--weights',required=True)
    p.add_argument('--backend',default='eigen')
    p.add_argument('--batch-size',type=int,default=8)
    a=p.parse_args()
    for go,mode in [('go nodes 100 movetime 3000','movetime'),
                    ('go wtime 180000 btime 180000 winc 2000 binc 2000 movestogo 30','clock')]:
        cmd=[a.engine,'--weights',a.weights,'--backend',a.backend,'--batch-size',str(a.batch_size),
             '--simulations','100','--tmax','5000']
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,text=True,bufsize=1)
        try:
            proc.stdin.write('uci\nisready\nposition startpos\n'+go+'\n');proc.stdin.flush()
            lines=[]
            while True:
                line=proc.stdout.readline()
                if not line:raise RuntimeError('AlphaZero exited before bestmove')
                lines.append(line.strip())
                if line.startswith('bestmove '):break
            proc.stdin.write('quit\n');proc.stdin.flush()
            _,err=proc.communicate(timeout=20)
            assert 'uciok' in lines and 'readyok' in lines
            assert any(x.startswith('info ') and ' nodes ' in x and ' nps ' in x for x in lines)
            assert all('⚙️' not in x and '🧠' not in x for x in lines)
            assert '⚙️ executable=' in err and '⚙️ network=' in err
            assert '🧠 AlphaZero analysis' in err and 'nn_ms=' in err and 'selection_ms=' in err
            assert f'mode={mode}' in err
            print('PASS',go)
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
    return 0
if __name__=='__main__':sys.exit(main())
