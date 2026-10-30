#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = aarch64 ] || { echo "Requires Debian ARM64 Raspberry Pi" >&2; exit 2; }
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/build_posix.sh" "$@"
