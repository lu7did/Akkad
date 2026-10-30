#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ $# -ge 1 ]] || { echo 'Usage: uci_smoke.sh /path/model.tflite' >&2; exit 2; }
MODEL="$(realpath "$1")"
python3 - "$HERE/run.sh" "$MODEL" <<'PY'
import subprocess,sys,time,threading,queue
script,model=sys.argv[1:]
p=subprocess.Popen(["bash",script,model,"--stdio"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
q=queue.Queue()
def reader(s, label):
 for line in s:q.put((label,line.rstrip()))
 q.put((label,None))
threading.Thread(target=reader,args=(p.stdout,"out"),daemon=True).start()
threading.Thread(target=reader,args=(p.stderr,"err"),daemon=True).start()
def stage(cmd,expect,timeout):
 print('>>>',cmd,flush=True);p.stdin.write(cmd+'\n');p.stdin.flush()
 until=time.monotonic()+timeout
 while time.monotonic()<until:
  try:kind,line=q.get(timeout=min(.5,max(.01,until-time.monotonic())))
  except queue.Empty:
   if p.poll() is not None:raise RuntimeError(f'process exited {p.returncode} before {expect}')
   continue
  if line is None:continue
  print(line,flush=True)
  if kind=='out' and line.startswith(expect):return
 raise TimeoutError('Timed out waiting for '+expect)
try:
 stage('uci','uciok',20);stage('isready','readyok',60)
 p.stdin.write('position startpos\n');p.stdin.flush()
 stage('go nodes 1','bestmove ',90)
 p.stdin.write('quit\n');p.stdin.flush();p.wait(timeout=10)
 if p.returncode:raise RuntimeError(f'Exit code {p.returncode}')
 print('UCI SMOKE OK')
finally:
 if p.poll() is None:p.kill();p.wait()
PY
