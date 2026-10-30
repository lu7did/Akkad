#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
EXE="$ROOT/build/AlphaZero"
[[ -x "$EXE" ]] || { echo "ERROR: ejecutable no encontrado: $EXE (ejecutar tools/bash/build.sh)" >&2; exit 2; }
WEIGHTS="${ALPHAZERO_WEIGHTS:-}"
if [[ $# -gt 0 && "${1:0:1}" != '-' ]]; then WEIGHTS="$1"; shift; fi
[[ -n "$WEIGHTS" && -f "$WEIGHTS" ]] || { echo 'Uso: run.sh /ruta/red.pb.gz [argumentos]. También ALPHAZERO_WEIGHTS=/ruta/red.pb.gz' >&2; exit 2; }
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
exec "$EXE" --weights "$WEIGHTS" --backend eigen --backend-options '' "$@"
