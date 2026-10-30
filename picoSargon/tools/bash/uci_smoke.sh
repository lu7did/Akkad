#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
printf 'uci\nisready\nposition startpos\ngo depth 2 movetime 2000\nquit\n' | "$HERE/run.sh"
