#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source="$root/src/native_bnn.cpp"
if [[ "$(uname -s)" == "Darwin" ]]; then
  output="$root/src/libpicobit_native.dylib"
  flags=(-dynamiclib)
else
  output="$root/src/libpicobit_native.so"
  flags=(-fPIC -shared)
fi
if [[ "$(uname -m)" == "x86_64" || "$(uname -m)" == "amd64" ]]; then
  flags+=(-mpopcnt)
fi
${CXX:-c++} -std=c++17 -O3 "${flags[@]}" "$source" -o "$output"
printf '✅ picoBit native binary: %s\n' "$output"
