#!/usr/bin/env bash
# Native AlphaZero UCI runner for macOS, v0.1.3
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AZ="$(cd -- "$HERE/../.." && pwd -P)"
AKKAD="$(cd -- "$AZ/.." && pwd -P)"
EXE="$AZ/build/AlphaZero"
SIMULATIONS=1000
TIMEOUT=60000
WEIGHTS="/Users/pedrocolla/akkad/AlphaZero/assets/t1-256x10-distilled-swa-2432500.pb.gz"
BACKEND=eigen
BACKEND_OPTIONS=''
usage() {
cat <<'HELP'
AlphaZero macOS UCI v0.1.3
Usage: run_alphazero.sh [--weights FILE] [--simulations N] [--timeout MS] [--help]
Defaults: simulations=1000, timeout=60000ms, backend=eigen (CPU).
         weights: ALPHAZERO_WEIGHTS or existing macOS emma weights in brains.json.
Notes: 'timeout' is the absolute per-search ceiling; TMax is the
       normal MCTS time budget (10000ms by default), also configurable via UCI.
       Standard UCI stdin/stdout; this is NOT a TCP listener.
HELP
}
if [[ $# -eq 1 && ( "$1" == --help || "$1" == -h ) ]]; then usage; exit 0; fi
while (( $# )); do
  case "$1" in
    --weights|--simulations|--timeout)
      (( $# >= 2 )) || { echo "ERROR: missing value for $1" >&2; exit 2; }
      case "$1" in --weights) WEIGHTS="$2";; --simulations) SIMULATIONS="$2";; --timeout) TIMEOUT="$2";; esac
      shift 2;;
    *) echo "ERROR: unknown argument $1" >&2; usage >&2; exit 2;;
  esac
done
[[ "$SIMULATIONS" =~ ^[0-9]+$ ]] && (( SIMULATIONS >= 1 && SIMULATIONS <= 10000000 )) || { echo 'ERROR: simulations out of range (1..10000000)' >&2; exit 2; }
[[ "$TIMEOUT" =~ ^[0-9]+$ ]] && (( TIMEOUT <= 3600000 )) || { echo 'ERROR: timeout out of range (0..3600000 ms)' >&2; exit 2; }
[[ -x "$EXE" ]] || { echo "ERROR: missing executable $EXE; first run tools/macOS/build.sh" >&2; exit 2; }
if [[ -z "$WEIGHTS" ]]; then
  # Resolve the existing emma profile, without modifying other platforms.
  WEIGHTS="$(python3 - "$AKKAD" <<'PY_WEIGHTS'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
f=root/'Sargon-NNUE/etc/brains/brains.json'
try:
    data=json.loads(f.read_text(encoding='utf-8'))['brains']['emma']['lc0-weights']
    if isinstance(data, dict): data=data.get('macos') or data.get('darwin') or ''
    if data:
        p=pathlib.Path(data).expanduser()
        if not p.is_absolute(): p=(root/'Sargon-NNUE'/p).resolve()
        if p.is_file(): print(p)
except (OSError,ValueError,KeyError,TypeError): pass
PY_WEIGHTS
)"
fi
[[ -n "$WEIGHTS" && -f "$WEIGHTS" ]] || { echo 'ERROR: weights not found. Specify --weights /path/network.pb.gz or ALPHAZERO_WEIGHTS' >&2; exit 2; }
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
exec "$EXE" --weights "$WEIGHTS" --backend "$BACKEND" --backend-options "$BACKEND_OPTIONS" --simulations "$SIMULATIONS" --timeout "$TIMEOUT"
