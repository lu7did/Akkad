#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BUILD="$ROOT/build-pico2_w"
usage(){ echo "Usage: $0 [--clean] [--help] (PICO_SDK_PATH is required)"; }
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then usage;exit 0; fi
if [ "${1:-}" = "--clean" ]; then rm -rf -- "$BUILD";shift;fi
if [ "$#" -ne 0 ]; then usage;exit 2;fi
: "${PICO_SDK_PATH:?Set PICO_SDK_PATH to an installed Pico SDK}"
cmake -S "$ROOT" -B "$BUILD" -G Ninja -DPICO_BOARD=pico2_w -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j 4
echo "UF2: $BUILD/picoAlphaARM.uf2"
