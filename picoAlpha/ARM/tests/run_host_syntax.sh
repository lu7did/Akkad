#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
"${CXX:-g++}" -std=c++17 -Wall -Wextra -DPICOALPHA_MDNS_COMPILED=1 \
  -I"$HERE/host_sdk_stub" -I"$ROOT/include" -I"$ROOT/assets" \
  -fsyntax-only "$ROOT/src/pico_main.cpp"
echo "PASS pico_main.cpp syntax with SDK-compatible stubs (not a Pico SDK build)"
