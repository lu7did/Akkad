#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ " $* " == *" --hive "* ]]; then
  exec python3 "$ROOT/src/hive.py" "$@"
else
  exec python3 "$ROOT/src/hive.py" --hive "$ROOT/etc/hive.yml" "$@"
fi
