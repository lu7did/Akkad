#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../debian/picoSargon" && pwd)"
cmake -S "$ROOT" -B "$ROOT/build" -DCMAKE_BUILD_TYPE=Release -DSTEROIDS="${STEROIDS:-ON}"
cmake --build "$ROOT/build" --parallel "${JOBS:-2}"
