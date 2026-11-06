#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
OUT="$(printf 'uci\nisready\nposition startpos\ngo depth 2 movetime 1000\nquit\n' | "$HERE/run.sh")"
printf '%s\n' "$OUT"
grep -q '^uciok$' <<< "$OUT"
grep -q '^readyok$' <<< "$OUT"
grep -Eq '^bestmove [a-h][1-8][a-h][1-8][qrbn]?$' <<< "$OUT"
echo 'PASS: UCI smoke test'
