#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEIGHTS="${1:-${ALPHAZERO_WEIGHTS:-}}"
if [[ -z "$WEIGHTS" ]]; then
  echo "Uso: uci_smoke.sh /ruta/red.pb.gz [nodos]" >&2
  exit 2
fi
if [[ ! -f "$WEIGHTS" ]]; then
  echo "ERROR: red no encontrada: $WEIGHTS" >&2
  exit 2
fi
NODES="${2:-8}"
if ! [[ "$NODES" =~ ^[1-9][0-9]*$ ]]; then
  echo 'ERROR: nodos debe ser un entero positivo' >&2
  exit 2
fi
export ALPHAZERO_SMOKE_HERE="$HERE" ALPHAZERO_SMOKE_WEIGHTS="$WEIGHTS" ALPHAZERO_SMOKE_NODES="$NODES"
python3 - <<'PY'
import os, subprocess, threading, queue, time, sys

cmd = [os.path.join(os.environ['ALPHAZERO_SMOKE_HERE'], 'run.sh'), os.environ['ALPHAZERO_SMOKE_WEIGHTS']]
nodes = int(os.environ['ALPHAZERO_SMOKE_NODES'])
responses = queue.Queue()
started = time.monotonic()
print('Ejecutable:', cmd[0], flush=True)
print('Red:', cmd[1], flush=True)
print('Nodos:', nodes, flush=True)
print('Iniciando motor...', flush=True)
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, bufsize=1)

def read_lines():
    try:
        for line in p.stdout:
            print(line, end='', flush=True)
            responses.put(line.rstrip('\r\n'))
    finally:
        responses.put(None)
threading.Thread(target=read_lines, daemon=True).start()

def send(command):
    if p.poll() is not None:
        raise RuntimeError(f'Motor terminó con código {p.returncode} antes de: {command}')
    print('>>>', command, flush=True)
    p.stdin.write(command + '\n')
    p.stdin.flush()

def until(label, predicate, timeout):
    deadline = time.monotonic() + timeout
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError(f'Timeout de {timeout}s esperando {label}; exit={p.poll()}')
        try:
            line = responses.get(timeout=min(left, 1.0))
        except queue.Empty:
            if p.poll() is not None and responses.empty():
                raise RuntimeError(f'Motor terminó con código {p.returncode} esperando {label}')
            continue
        if line is None:
            raise RuntimeError(f'Fin de salida; motor exit={p.poll()} esperando {label}')
        if predicate(line):
            print(f'<<< {label} OK ({time.monotonic()-started:.2f}s desde inicio)', flush=True)
            return

try:
    send('uci')
    until('uciok', lambda x: x.strip() == 'uciok', 60)
    send('isready')
    until('readyok', lambda x: x.strip() == 'readyok', 180)
    send('ucinewgame')
    send('position startpos')
    send(f'go nodes {nodes}')
    until('bestmove', lambda x: x.startswith('bestmove ') and x.split()[1] not in ('(none)', '0000'), 240)
    print('SMOKE OK: inicialización y búsqueda UCI completas', flush=True)
except Exception as exc:
    print(f'SMOKE FAIL: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
    sys.exit(1)
finally:
    if p.poll() is None:
        try:
            p.stdin.write('quit\n')
            p.stdin.flush()
            p.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            p.kill()
            p.wait()
PY
