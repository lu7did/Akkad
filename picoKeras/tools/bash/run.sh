#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${HERE}/../.." && pwd)"
EXE="${ROOT}/debian/build/picoKeras"
[[ -x "$EXE" ]] || { echo "Missing executable: $EXE" >&2; exit 1; }
[[ $# -gt 0 ]] || { echo 'Usage: run.sh /path/model.tflite [--stdio|--host IP --port N]' >&2; exit 2; }
MODEL="$1";shift
[[ -f "$MODEL" ]] || { echo "Missing model: $MODEL" >&2; exit 1; }
exec "$EXE" --network "$MODEL" "$@"
