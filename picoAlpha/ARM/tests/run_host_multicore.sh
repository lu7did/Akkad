#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BUILD="${TMPDIR:-/tmp}/picoalpha-arm-hosttest"
mkdir -p "$BUILD"
"${CXX:-g++}" -std=c++17 -O2 -pthread -Wall -Wextra \
 -I"$HERE/host_sdk_stub" -I"$ROOT/include" -I"$ROOT/assets" \
 "$ROOT/src/board.cpp" "$ROOT/src/nnue_int8.cpp" "$ROOT/src/mcts_arm.cpp" \
 "$ROOT/src/search_coordinator.cpp" "$HERE/host_multicore_test.cpp" \
 -o "$BUILD/host_multicore_test"
"$BUILD/host_multicore_test"
