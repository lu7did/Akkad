#!/usr/bin/env bash
# Akkad/AlphaZero/tools/bash/build.sh
# Wrapper compatible con la estructura unificada de AlphaZero.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
BUILDER="$ROOT/build.sh"

if [[ ! -f "$BUILDER" ]]; then
  printf 'ERROR: no existe el constructor principal: %s\n' "$BUILDER" >&2
  exit 2
fi

# Invocar a traves de bash: el ZIP puede no preservar el bit ejecutable.
if (( $# == 0 )); then
  exec bash "$BUILDER" --OS RBPi
fi
exec bash "$BUILDER" "$@"
