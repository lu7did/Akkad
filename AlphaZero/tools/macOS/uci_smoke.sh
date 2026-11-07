#!/usr/bin/env bash
# AlphaZero macOS UCI smoke test v0.2.0
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUN="$HERE/run_alphazero.sh"
WEIGHTS="${ALPHAZERO_WEIGHTS:-}"
SIMULATIONS=8
TIMEOUT=15000
STARTUP_TIMEOUT=180
SEARCH_TIMEOUT=60
usage() {
cat <<'HELP'
AlphaZero macOS UCI smoke test v0.2.0
Usage: uci_smoke.sh [--weights FILE] [--simulations N] [--timeout MS]
                    [--startup-timeout SEC] [--search-timeout SEC] [--help]
Defaults: simulations=8, timeout=15000 ms, startup-timeout=180 s,
          search-timeout=60 s. Network from ALPHAZERO_WEIGHTS or emma profile.
Checks: uciok, readyok, info and a legal-format bestmove.
Only performs UCI stdin/stdout; no TCP server is started.
HELP
}
while (( $# )); do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --weights|--simulations|--timeout|--startup-timeout|--search-timeout)
      (( $# >= 2 )) || { echo "ERROR: missing value for $1" >&2; exit 2; }
      case "$1" in
        --weights) WEIGHTS="$2";;
        --simulations) SIMULATIONS="$2";;
        --timeout) TIMEOUT="$2";;
        --startup-timeout) STARTUP_TIMEOUT="$2";;
        --search-timeout) SEARCH_TIMEOUT="$2";;
      esac
      shift 2 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
for v in SIMULATIONS TIMEOUT STARTUP_TIMEOUT SEARCH_TIMEOUT; do
  value="${!v}"
  [[ "$value" =~ ^[0-9]+$ ]] || { echo "ERROR: $v must be an integer" >&2; exit 2; }
done
(( SIMULATIONS >= 1 && SIMULATIONS <= 10000000 )) || { echo 'ERROR: simulations outside 1..10000000' >&2; exit 2; }
(( TIMEOUT >= 1 && TIMEOUT <= 3600000 )) || { echo 'ERROR: timeout outside 1..3600000' >&2; exit 2; }
(( STARTUP_TIMEOUT >= 1 && SEARCH_TIMEOUT >= 1 )) || { echo 'ERROR: timeouts must be positive' >&2; exit 2; }
[[ -f "$RUN" ]] || { echo "ERROR: runner absent: $RUN (restore run_alphazero.sh from this patch)" >&2; exit 2; }
[[ -r "$RUN" ]] || { echo "ERROR: runner unreadable: $RUN" >&2; exit 2; }
command -v python3 >/dev/null || { echo 'ERROR: python3 not found' >&2; exit 2; }
export AZ_SMOKE_RUN="$RUN" AZ_SMOKE_WEIGHTS="$WEIGHTS" AZ_SMOKE_SIMS="$SIMULATIONS" \
  AZ_SMOKE_TIMEOUT="$TIMEOUT" AZ_SMOKE_STARTUP="$STARTUP_TIMEOUT" AZ_SMOKE_SEARCH="$SEARCH_TIMEOUT"
python3 - <<'PY'
import os, queue, re, subprocess, sys, threading, time
# Invoke through bash so ZIP extraction need not preserve executable bits.
cmd = ['/bin/bash', os.environ['AZ_SMOKE_RUN'], '--simulations', os.environ['AZ_SMOKE_SIMS'],
       '--timeout', os.environ['AZ_SMOKE_TIMEOUT']]
if os.environ['AZ_SMOKE_WEIGHTS']:
    cmd += ['--weights', os.environ['AZ_SMOKE_WEIGHTS']]
startup = int(os.environ['AZ_SMOKE_STARTUP'])
search = int(os.environ['AZ_SMOKE_SEARCH'])
q = queue.Queue()
p = None

def reader(stream, label, events=False):
    try:
        for raw in stream:
            s = raw.rstrip('\r\n')
            print(f'{label} {s}', flush=True)
            if events:
                q.put(s)
    finally:
        if events:
            q.put(None)

def send(s):
    if p.poll() is not None:
        raise RuntimeError(f'engine exited ({p.returncode}) before {s!r}')
    print('>>>', s, flush=True)
    p.stdin.write(s + '\n')
    p.stdin.flush()

def wait_for(name, predicate, seconds):
    deadline = time.monotonic() + seconds
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError(f'{name} not received within {seconds}s')
        try:
            line = q.get(timeout=min(left, 0.5))
        except queue.Empty:
            if p.poll() is not None and q.empty():
                raise RuntimeError(f'engine exited ({p.returncode}) while waiting for {name}')
            continue
        if line is None:
            raise RuntimeError(f'engine stdout closed while waiting for {name}')
        if line.startswith('info string ERROR'):
            raise RuntimeError(line)
        if predicate(line):
            return line

try:
    print('SMOKE: macOS AlphaZero UCI, simulations={}, timeout={}ms'.format(
        os.environ['AZ_SMOKE_SIMS'], os.environ['AZ_SMOKE_TIMEOUT']), flush=True)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1)
    threading.Thread(target=reader, args=(p.stdout, 'UCI:', True), daemon=True).start()
    threading.Thread(target=reader, args=(p.stderr, 'ERR:', False), daemon=True).start()
    send('uci')
    wait_for('uciok', lambda x: x.strip() == 'uciok', startup)
    send('isready')
    wait_for('readyok', lambda x: x.strip() == 'readyok', startup)
    send('ucinewgame')
    send('position startpos')
    send('go nodes ' + os.environ['AZ_SMOKE_SIMS'])
    seen_info = [False]
    def is_best(line):
        if line.startswith('info '):
            seen_info[0] = True
        return line.startswith('bestmove ')
    best = wait_for('bestmove', is_best, search)
    if not seen_info[0]:
        raise RuntimeError('bestmove received but no UCI info frame')
    move = best.split()[1] if len(best.split()) > 1 else ''
    if not re.fullmatch(r'[a-h][1-8][a-h][1-8][qrbn]?', move):
        raise RuntimeError('invalid bestmove: ' + best)
    print('PASS: uciok, readyok, bestmove ' + move, flush=True)
except Exception as e:
    print(f'FAIL: {type(e).__name__}: {e}', file=sys.stderr, flush=True)
    sys.exit(1)
finally:
    if p is not None:
        if p.poll() is None:
            try:
                p.stdin.write('quit\n'); p.stdin.flush()
                p.wait(timeout=5)
            except (OSError, BrokenPipeError, subprocess.TimeoutExpired):
                p.kill(); p.wait()
        for stream in (p.stdin, p.stdout, p.stderr):
            try: stream.close()
            except OSError: pass
PY
