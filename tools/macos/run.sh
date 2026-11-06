#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$HERE/../.." && pwd -P)"
ENGINE="$ROOT/picoSargon/macOS/build/picoSargon"
WEIGHTS="$ROOT/picoSargon/x86/picoSargon/assets/grumpy.bin"
[[ -x "$ENGINE" ]] || { echo "Falta $ENGINE. Compilar con: $ROOT/picoSargon/macOS/build.sh" >&2; exit 1; }
[[ -f "$WEIGHTS" ]] || { echo "Falta la red: $WEIGHTS" >&2; exit 1; }
exec "$ENGINE" --weights "$WEIGHTS" "$@"
