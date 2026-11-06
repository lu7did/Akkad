#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENGINE="$HERE/build/picoSargon"
WEIGHTS="$HERE/../../x86/picoSargon/assets/grumpy.bin"
[[ -x "$ENGINE" ]] || { echo 'Falta picoSargon. Ejecutar ./build.sh' >&2;exit 1; }
[[ -f "$WEIGHTS" ]] || { echo "Falta la red: $WEIGHTS" >&2;exit 1; }
exec "$ENGINE" --weights "$WEIGHTS" "$@"
