#!/usr/bin/env bash
# Native Debian/Raspberry Pi ARM64 build, shared C++ core with Windows.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ "$(uname -s)" == Linux && "$(uname -m)" == aarch64 ]] || { echo 'ERROR: se requiere Linux ARM64 (aarch64)' >&2; exit 2; }
[[ -f /etc/os-release ]] && { . /etc/os-release; echo "OS: ${PRETTY_NAME:-Linux ARM64}"; }
if [[ "${SKIP_APT:-0}" != 1 ]]; then
  command -v apt-get >/dev/null || { echo 'ERROR: apt-get no disponible; SKIP_APT=1 para administrar dependencias manualmente' >&2; exit 2; }
  if [[ "${EUID}" == 0 ]]; then SUDO=(); else command -v sudo >/dev/null || { echo 'ERROR: sudo no disponible' >&2; exit 2; }; SUDO=(sudo); fi
  "${SUDO[@]}" apt-get update
  DEBIAN_FRONTEND=noninteractive "${SUDO[@]}" apt-get install -y --no-install-recommends \
    build-essential git ca-certificates cmake meson ninja-build pkg-config python3 \
    protobuf-compiler libprotobuf-dev libopenblas-dev libeigen3-dev zlib1g-dev libssl-dev
fi
for cmd in git meson ninja python3 pkg-config g++; do command -v "$cmd" >/dev/null || { echo "ERROR: dependencia ausente: $cmd" >&2; exit 2; }; done
pkg-config --exists openblas || { echo 'ERROR: falta desarrollo OpenBLAS' >&2; exit 2; }
exec "$HERE/build_posix.sh" "$@"
