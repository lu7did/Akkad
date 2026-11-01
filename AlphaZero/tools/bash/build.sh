#!/usr/bin/env bash
# Compatibility wrapper for the unified AlphaZero builder.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
# Default to Raspberry Pi for historical callers. Allow explicit --OS choice.
if (( $# == 0 )); then
  exec "$ROOT/build.sh" --OS RBPi
fi
exec "$ROOT/build.sh" "$@"
