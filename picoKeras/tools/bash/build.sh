#!/usr/bin/env bash
# picoKeras Debian build v0.2.6
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
SRC="$ROOT/debian"
BUILD="$SRC/build"
TF="${TFLITE_ROOT:-$SRC/third_party/tensorflow}"
TF_VERSION="${TF_VERSION:-v2.18.1}"
JOBS="${BUILD_JOBS:-1}"
if [[ "${1:-}" == '--help' || "${1:-}" == '-h' ]]; then
  echo 'Usage: build.sh [--help] (environment: TFLITE_ROOT, TF_VERSION, BUILD_JOBS, INSTALL_DEPS=0, CLEAN_BUILD=1)'
  echo 'Builds from picoKeras/src with TFLite backend in picoKeras/debian/build'
  exit 0
fi
[[ $# -eq 0 ]] || { echo "Unknown argument: $1" >&2;exit 2; }
[[ "$(uname -s)" == Linux ]] || { echo 'Linux required' >&2;exit 2; }
for tool in cmake git c++;do
 if ! command -v "$tool" >/dev/null; then
  if [[ "${INSTALL_DEPS:-1}" == 1 ]];then
   sudo apt-get update
   sudo apt-get install -y --no-install-recommends build-essential cmake ninja-build git python3 pkg-config libflatbuffers-dev flatbuffers-compiler libabsl-dev libeigen3-dev zlib1g-dev
   break
  else echo "Missing $tool" >&2;exit 1;fi
 fi
done
if [[ ! -f "$TF/tensorflow/lite/CMakeLists.txt" ]]; then
 if [[ "$TF" != "$SRC/third_party/tensorflow" ]];then echo "Invalid external TFLITE_ROOT=$TF" >&2;exit 1;fi
 mkdir -p "$(dirname "$TF")"
 git clone --depth 1 --branch "$TF_VERSION" https://github.com/tensorflow/tensorflow.git "$TF"
fi
if [[ "${CLEAN_BUILD:-0}" == 1 ]];then rm -rf "$BUILD";fi
if [[ -f "$BUILD/CMakeCache.txt" ]]; then
  src_cached="$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$BUILD/CMakeCache.txt" | head -1)"
  if [[ "$src_cached" != "$SRC" ]];then rm -rf "$BUILD";fi
fi
if command -v ninja >/dev/null;then
 cmake -S "$SRC" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DTFLITE_ROOT="$TF"
else
 cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DTFLITE_ROOT="$TF"
fi
cmake --build "$BUILD" --target picoKeras --parallel "$JOBS"
echo "Built picoKeras Debian: $BUILD/picoKeras"
