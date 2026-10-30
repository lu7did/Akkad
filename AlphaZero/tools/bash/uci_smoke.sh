#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEIGHTS="${1:-${ALPHAZERO_WEIGHTS:-}}"
[[ -n "$WEIGHTS" ]] || { echo 'Uso: uci_smoke.sh /ruta/red.pb.gz' >&2; exit 2; }
shift $(( $# > 0 ? 1 : 0 ))
export WEIGHTS HERE
python3 - <<'PY'
import os, subprocess, selectors, time, sys
cmd=[os.path.join(os.environ['HERE'],'run.sh'),os.environ['WEIGHTS']]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
selector=selectors.DefaultSelector();selector.register(p.stdout, selectors.EVENT_READ)
def wait_for(expected, limit=90):
    end=time.monotonic()+limit
    while time.monotonic()<end:
        if p.poll() is not None and not selector.select(timeout=0):
            raise RuntimeError(f'Proceso terminó con código {p.returncode} esperando {expected}')
        if selector.select(timeout=min(1,max(.01,end-time.monotonic()))):
            line=p.stdout.readline()
            if not line: raise RuntimeError('EOF esperando '+expected)
            print(line,end='',flush=True)
            if line.strip()==expected or (expected=='bestmove' and line.startswith('bestmove ')):
                return
    raise TimeoutError('Timeout esperando '+expected)
try:
    for cmd,expected in [('uci','uciok'),('isready','readyok'),('position startpos',None),('go nodes 30','bestmove')]:
        p.stdin.write(cmd+'\n');p.stdin.flush()
        if expected: wait_for(expected)
    print('SMOKE OK')
finally:
    if p.poll() is None:
        try:p.stdin.write('quit\n');p.stdin.flush();p.wait(timeout=5)
        except Exception:p.kill();p.wait()
PY
