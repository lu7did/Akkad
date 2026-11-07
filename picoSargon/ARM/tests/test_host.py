import pathlib, subprocess, sys
exe=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path('build-host/picoSargon_host')
for depth,expected in ((1,20),(2,400),(3,8902)):
 p=subprocess.run([str(exe),'--perft',str(depth)],capture_output=True,text=True,check=True)
 assert f'perft={expected}' in p.stdout,(depth,p.stdout,p.stderr)
 print('PERFT depth=%s nodes=%s OK'%(depth,expected))
net=pathlib.Path(__file__).resolve().parents[1]/'assets/grumpy.bin'
p=subprocess.run([str(exe),str(net)],input='uci\nisready\nposition startpos\ngo\nquit\n',capture_output=True,text=True,check=True,timeout=90)
assert 'uciok' in p.stdout and 'readyok' in p.stdout and 'bestmove ' in p.stdout
print('UCI HOST OK',p.stdout[-140:])
