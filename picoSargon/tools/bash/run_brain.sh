#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
BRAINS="${BRAINS:-$ROOT/Sargon-NNUE/data/brains/brains.json}"
ID="${1:-tinySargon}"; shift || true
exec "$ROOT/picoSargon/debian/picoSargon/build/picoSargon" --brains "$BRAINS" --brain "$ID" "$@"
