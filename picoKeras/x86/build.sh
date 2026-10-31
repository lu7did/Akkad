#!/usr/bin/env bash
set -euo pipefail
: "${TENSORFLOW_ROOT:?Set TENSORFLOW_ROOT to the TensorFlow C distribution root}"
cmake -S "$(dirname "$0")" -B "$(dirname "$0")/build" -DCMAKE_BUILD_TYPE=Release -DTENSORFLOW_ROOT="$TENSORFLOW_ROOT"
cmake --build "$(dirname "$0")/build" -j
