#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../debian/picoSargon" && pwd)"
exec "$ROOT/build/picoSargon" --weights "$ROOT/assets/grumpy.bin" "$@"
