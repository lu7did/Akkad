#!/usr/bin/env bash
# AlphaZero macOS build wrapper - v0.1.3
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../.." && pwd -P)"
usage() {
  cat <<'HELP'
AlphaZero macOS build v0.1.3
Usage: build.sh [--help]
Builds the shared AlphaZero C++ engine for native macOS Apple Silicon.
Environment: BUILD_JOBS=N, LC0_REF=v0.32.1, LC0_SOURCE=PATH,
             CLEAN_BUILD=1 (regenerate Meson build directory).
Output: AlphaZero/build/AlphaZero
Requires Xcode command-line tools, git, cmake, meson, ninja, python3,
         and the LC0 build dependencies.
HELP
}
if (( $# > 0 )); then
  case "$1" in -h|--help) [[ $# -eq 1 ]] || exit 2; usage; exit 0;; *) usage >&2; exit 2;; esac
fi
[[ "$(uname -s)" == Darwin ]] || { echo 'ERROR: requires macOS' >&2; exit 2; }
exec bash "$ROOT/build.sh" --OS MacOS
