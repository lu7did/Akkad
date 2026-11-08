#!/usr/bin/env bash
# AlphaZero macOS UCI smoke test v0.2.9
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AZ="$(cd -- "$HERE/../.." && pwd -P)"
ROOT="$(cd -- "$AZ/.." && pwd -P)"
ENGINE="$AZ/macOS/build/AlphaZero"
WEIGHTS="${ALPHAZERO_WEIGHTS:-}"
BRAIN=emma
NODES=8
CORES=1
PYTHON="${PYTHON_BIN:-python3}"
usage() { echo 'Usage: test_smoke.sh [--weights FILE] [--brain ID] [--nodes N] [--cores N] [--python EXE] [--help]'; }
while (( $# )); do
 case "$1" in
   --help|-h) usage; exit 0;;
   --weights|--brain|--nodes|--cores|--python)
     (( $# >= 2 )) || { echo "ERROR: missing value for $1" >&2; exit 2; }
     case "$1" in --weights) WEIGHTS="$2";; --brain) BRAIN="$2";; --nodes) NODES="$2";; --cores) CORES="$2";; --python) PYTHON="$2";; esac
     shift 2;;
   *) echo "ERROR: unknown option: $1" >&2; exit 2;;
 esac
done
[[ "$NODES" =~ ^[1-9][0-9]*$ && "$CORES" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: nodes and cores must be positive integers' >&2; exit 2; }
if [[ -z "$WEIGHTS" ]]; then
 WEIGHTS="$("$PYTHON" - "$ROOT" "$BRAIN" 'macOS' <<'PY_WEIGHTS'
import json, pathlib, sys
root, brain, platform = pathlib.Path(sys.argv[1]),sys.argv[2],sys.argv[3]
try:
    data=json.loads((root/'Sargon-NNUE/etc/brains/brains.json').read_text())['brains'][brain]['lc0-weights']
    if isinstance(data,dict): data=data.get('macos' if platform=='macOS' else 'debian','')
    path=pathlib.Path(data).expanduser()
    if not path.is_absolute(): path=(root/'Sargon-NNUE'/path).resolve()
    if path.is_file(): print(path)
except (OSError,KeyError,ValueError,TypeError): pass
PY_WEIGHTS
 )"
fi
[[ -f "$WEIGHTS" ]] || { echo "ERROR: weights not found for brain $BRAIN (use --weights)" >&2; exit 2; }
[[ -x "$ENGINE" ]] || { echo "ERROR: missing engine $ENGINE (run build.sh)" >&2; exit 2; }
exec "$PYTHON" "$AZ/tests/uci_transport_smoke.py" --engine "$ENGINE" --weights "$WEIGHTS" --backend eigen --nodes "$NODES" --cores "$CORES"
