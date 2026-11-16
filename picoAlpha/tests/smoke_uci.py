#!/usr/bin/env python3
"""Run portable C++ UCI sanity test against a deterministic INT8 test model."""
import os,struct,subprocess,sys,tempfile

def main(binary):
    with tempfile.TemporaryDirectory() as td:
        model=os.path.join(td,'synthetic.bin')
        # Same binary format, zero INT8 matrices, finite positive scales.
        open(model,'wb').write(b'PANNI8\r\n'+struct.pack('<III4f',1,780,16,*([0.01]*4))+bytes(14544))
        commands='uci\nisready\nposition startpos\ngo depth 4 movetime 1000 nodes 16\n'
        # Interactive stdin to keep engine alive until asynchronous bestmove arrives.
        p=subprocess.Popen([binary,'--network',model,'--depth','4','--sim','16','--timeout','1000'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        import time
        for command in commands.splitlines():p.stdin.write(command+'\n');p.stdin.flush()
        # Give the search process a short time to finish, then shut down cleanly.
        time.sleep(0.25)
        p.stdin.write('quit\n');p.stdin.flush()
        output,errors=p.communicate(timeout=10)
        assert p.returncode==0,(output,errors)
        assert 'uciok' in output and 'readyok' in output,(output,errors)
        # quit can preempt search, so bestmove should still be emitted on stop.
        assert 'bestmove ' in output and 'info depth ' in output,(output,errors)
        print('PASS UCI basic/INT8 model, output:',output.replace('\n',' | '))
if __name__=='__main__':main(sys.argv[1])
