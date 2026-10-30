#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo "Requires native macOS Apple Silicon arm64" >&2; exit 2; }
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/build_posix.sh" "$@"
