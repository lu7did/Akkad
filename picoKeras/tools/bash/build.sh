#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${HERE}/../.." && pwd)"
SRC="${ROOT}/debian"
BUILD="${SRC}/build"
TF="${ROOT}/debian/third_party/tensorflow"
TF_VERSION="${TF_VERSION:-v2.18.1}"
JOBS="${BUILD_JOBS:-1}"
[[ $(uname -s) == Linux ]] || { echo 'Linux required' >&2; exit 1; }
[[ $(uname -m) == aarch64 ]] || { echo 'Expected aarch64 Debian' >&2; exit 1; }
if [[ ${INSTALL_DEPS:-1} == 1 ]]; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends build-essential cmake ninja-build git python3 python3-pip pkg-config libflatbuffers-dev flatbuffers-compiler libabsl-dev libeigen3-dev zlib1g-dev
fi
if [[ ! -d ${TF}/.git ]]; then
  mkdir -p "$(dirname "$TF")"
  git clone --depth 1 --branch "$TF_VERSION" https://github.com/tensorflow/tensorflow.git "$TF"
fi
if [[ ${CLEAN_BUILD:-0} == 1 ]]; then rm -rf "$BUILD"; fi
cmake -S "$SRC" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DTFLITE_ROOT="$TF"
cmake --build "$BUILD" --target picoKeras --parallel "$JOBS"
echo "Binary: ${BUILD}/picoKeras"
