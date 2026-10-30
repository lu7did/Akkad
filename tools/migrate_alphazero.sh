#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f AlphaZero/build_posix.sh ] || { echo 'Extract patch to Akkad root first' >&2; exit 2; }
if git ls-files 'Sargon-NNUE/x86/AlphaZero/' | grep -q .; then
  git rm -r -- Sargon-NNUE/x86/AlphaZero
fi
git add -- AlphaZero .gitignore
echo 'Review: git diff --cached --stat'
