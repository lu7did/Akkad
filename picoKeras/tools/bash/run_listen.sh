#!/usr/bin/env bash
# picoKeras Debian TCP listener v0.2.6
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
if [[ "${1:-}" == '--help' || $# -eq 0 ]]; then
 echo 'Usage: run_listen.sh /path/to/model.tflite [--host IP] [--port N]';exit 0
fi
MODEL="$1"; shift
[[ -f "$MODEL" && "$MODEL" == *.tflite ]] || { echo "Missing .tflite model: $MODEL" >&2;exit 1; }
EXE="$ROOT/debian/build/picoKeras"
[[ -x "$EXE" ]] || { echo "Build picoKeras Debian first: $EXE" >&2; exit 1; }
exec "$EXE" --weights "$(realpath "$MODEL")" --tcp "$@"
