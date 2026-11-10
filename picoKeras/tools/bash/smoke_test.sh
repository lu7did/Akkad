#!/usr/bin/env bash
# picoKeras Debian UCI smoke test v0.2.6
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
if [[ "${1:-}" == '--help' || $# -eq 0 ]];then echo 'Usage: smoke_test.sh /path/to/model.tflite';exit 0;fi
[[ $# -eq 1 && -f "$1" ]] || { echo 'Expected existing .tflite file' >&2; exit 2; }
python3 "$ROOT/tools/smoke_uci.py" --engine "$ROOT/debian/build/picoKeras" --weights "$(realpath "$1")"
