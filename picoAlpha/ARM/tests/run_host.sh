#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BUILD="${TMPDIR:-/tmp}/picoalpha-arm-hosttest"
mkdir -p "$BUILD"
"${CXX:-g++}" -std=c++17 -O2 -Wall -Wextra -I"$ROOT/include" -I"$ROOT/assets" \
 "$ROOT/src/board.cpp" "$ROOT/src/nnue_int8.cpp" "$ROOT/src/mcts_arm.cpp" \
 "$HERE/host_core_test.cpp" -o "$BUILD/host_core_test"
"$BUILD/host_core_test"
